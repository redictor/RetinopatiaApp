import os
import numpy as np
import cv2

import onnxruntime as ort

import torch
import timm
import torch.nn.functional as F


STAGE_NAMES = ["0", "1", "2", "3", "4"]  # можешь заменить на "No DR", "Mild", ...


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    e = np.exp(x)
    return e / (np.sum(e) + 1e-9)


class LocalRetinaModel:
    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir

        onnx_path = os.path.join(models_dir, "dr_stage.onnx")
        pt_path = os.path.join(models_dir, "best_cls.pt")

        if not os.path.exists(onnx_path):
            raise FileNotFoundError(f"Не найден {onnx_path}")
        if not os.path.exists(pt_path):
            raise FileNotFoundError(f"Не найден {pt_path}")

        # ONNX (stage)
        self.ort_sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

        # PyTorch (Grad-CAM)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_model = timm.create_model("tf_efficientnet_b0", pretrained=False, num_classes=5)
        sd = torch.load(pt_path, map_location="cpu")
        self.torch_model.load_state_dict(sd)
        self.torch_model.eval().to(self.device)

        # target layer for Grad-CAM
        self._target_layer = self.torch_model.conv_head

        self._act = None
        self._grad = None
        self._hooks_set = False

    def _ensure_hooks(self):
        if self._hooks_set:
            return

        def fwd_hook(_, __, out):
            self._act = out

        def bwd_hook(_, gin, gout):
            self._grad = gout[0]

        self._target_layer.register_forward_hook(fwd_hook)
        self._target_layer.register_full_backward_hook(bwd_hook)
        self._hooks_set = True

    def _preprocess_np(self, image_path: str, size=224) -> np.ndarray:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Не удалось прочитать изображение")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))[None, ...]  # 1x3xHxW
        return img

    def _preprocess_torch(self, image_path: str, size=224) -> torch.Tensor:
        x = self._preprocess_np(image_path, size=size)
        return torch.from_numpy(x)

    def predict_stage(self, image_path: str):
        x = self._preprocess_np(image_path, 224)
        logits = self.ort_sess.run(None, {"image": x})[0][0]  # (5,)
        probs = _softmax(logits)
        stage_id = int(np.argmax(probs))
        return stage_id, probs

    def gradcam_heatmap(self, image_path: str, class_idx: int | None = None) -> np.ndarray:
        self._ensure_hooks()

        x = self._preprocess_torch(image_path, 224).to(self.device)
        x.requires_grad_(True)

        logits = self.torch_model(x)
        if class_idx is None:
            class_idx = int(torch.argmax(logits, dim=1).item())

        score = logits[:, class_idx].sum()
        self.torch_model.zero_grad(set_to_none=True)
        score.backward()

        # Grad-CAM
        w = self._grad.mean(dim=(2, 3), keepdim=True)           # 1xCx1x1
        cam = (w * self._act).sum(dim=1, keepdim=True)          # 1x1xhxw
        cam = F.relu(cam)
        cam = F.interpolate(cam, size=(224, 224), mode="bilinear", align_corners=False)
        cam = cam[0, 0].detach().cpu().numpy()
        cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-6)
        return cam


# удобная “глобальная” модель (лениво грузим)
_model: LocalRetinaModel | None = None

def get_model() -> LocalRetinaModel:
    global _model
    if _model is None:
        _model = LocalRetinaModel(models_dir="models")
    return _model