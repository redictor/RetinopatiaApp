# infer_torch.py
import os
import sys
import json
import numpy as np
import cv2

def imread_unicode(path: str):
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return img

def preprocess(image_path: str, size=224):
    bgr = imread_unicode(image_path)
    if bgr is None:
        raise RuntimeError("Не удалось прочитать изображение")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)
    x = rgb.astype(np.float32) / 255.0
    x = np.transpose(x, (2, 0, 1))[None, ...] 
    return x

def main():
    if len(sys.argv) < 3:
        print("Usage: python infer_torch.py <image_path> <out_heatmap_png>", file=sys.stderr)
        sys.exit(2)

    image_path = sys.argv[1]
    out_png = sys.argv[2]

    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

    import torch
    import timm
    import torch.nn.functional as F

    models_dir = "models"
    pt_path = os.path.join(models_dir, "best_cls.pt")
    if not os.path.exists(pt_path):
        raise FileNotFoundError(f"Не найден {pt_path}")

    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = timm.create_model("tf_efficientnet_b0", pretrained=False, num_classes=5)
    sd = torch.load(pt_path, map_location="cpu")
    model.load_state_dict(sd)
    model.eval().to(device)

    target_layer = model.conv_head
    act = None
    grad = None

    def fwd_hook(_, __, out):
        nonlocal act
        act = out

    def bwd_hook(_, gin, gout):
        nonlocal grad
        grad = gout[0]

    target_layer.register_forward_hook(fwd_hook)
    target_layer.register_full_backward_hook(bwd_hook)

    x_np = preprocess(image_path, 224)
    x = torch.from_numpy(x_np).to(device)
    x.requires_grad_(True)

    logits = model(x)
    probs = torch.softmax(logits[0], dim=0).detach().cpu().numpy()
    stage_id = int(np.argmax(probs))

    score = logits[:, stage_id].sum()
    model.zero_grad(set_to_none=True)
    score.backward()

    w = grad.mean(dim=(2, 3), keepdim=True)
    cam = (w * act).sum(dim=1, keepdim=True)
    cam = F.relu(cam)
    cam = F.interpolate(cam, size=(224, 224), mode="bilinear", align_corners=False)
    cam = cam[0, 0].detach().cpu().numpy()
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-6)

    heat_u8 = (cam * 255).astype(np.uint8)
    cv2.imencode(".png", heat_u8)[1].tofile(out_png)

    print(json.dumps({
        "stage_id": stage_id,
        "p_max": float(np.max(probs)),
        "probs": [float(x) for x in probs],
        "heatmap_png": out_png,
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
