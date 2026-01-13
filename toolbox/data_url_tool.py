import os
import base64
import mimetypes
from pathlib import Path
from typing import Dict, Any

from virtual_server.cloud_disk import CloudDisk

# TODO: support more file types beyond image
class ReadAsDataURL:
    MAX_BYTES = 10 * 1024 * 1024  # 10MB limit
    ALLOWED_MIME_PREFIXES = ("image/png", "image/jpeg", "image/webp")

    def __init__(self, cloud_disk: "CloudDisk"):
        self.cloud_disk = cloud_disk
        self.workspace_path = cloud_disk.root_path.parent / 'workspace'

    def __call__(self, file_path: str, text: str = "") -> Dict[str, Any]:
        """
        Reads a local or cloud disk image file and converts it into a Data URL for multimodal analysis.
        The tool will first search for the file in the local workspace, and if not found, will then search the cloud disk.

        Args:
            file_path: The path to the image file. This can be a local path (if you've downloaded the file) or a relative path on the cloud disk.
                       For example: 'heatmap.png' (local) or 'ads/heatmap.png' (cloud).
            text: Optional text to be attached alongside the image for the model's analysis.

        Returns:
            A JSON object containing `attach_user_message`, which the environment will append as a user message.
        """
        # real_path = (self.cloud_disk.root_path / file_path).resolve()
        # if not real_path.exists() or not real_path.is_file():
        #     return {"error": f"File not found: {file_path}"}

        local_path =  (self.workspace_path / file_path).resolve()

        cloud_path = (self.cloud_disk.root_path / file_path).resolve()

        if local_path.exists() and local_path.is_file():
            real_path = local_path
        elif cloud_path.exists() and cloud_path.is_file():
            real_path = cloud_path
        else:
            return {"error": f"File not found in local workspace ('{local_path}') or cloud disk ('{cloud_path}'), please check the file path."}

        try:
            size = os.path.getsize(real_path)
            if size > self.MAX_BYTES:
                return {"error": f"File too large: {size} bytes, limit {self.MAX_BYTES} bytes"}
        except Exception:
            pass

        mime, _ = mimetypes.guess_type(str(real_path))
        if not mime:
            # fallback by extension
            ext = real_path.suffix.lower()
            if ext in (".png",):
                mime = "image/png"
            elif ext in (".jpg", ".jpeg"):
                mime = "image/jpeg"
            elif ext in (".webp",):
                mime = "image/webp"
            else:
                # If the extension is not a known image type, return an error.
                return {"error": f"File '{real_path}' is not a supported image file. Please provide a path to a PNG, JPEG, or WebP file."}

        # Double-check if the determined MIME type is in the allowed list.
        if not any(mime.startswith(p) for p in self.ALLOWED_MIME_PREFIXES):
            return {"error": f"Unsupported MIME type '{mime}' for file '{file_path}'. Only PNG, JPEG, and WebP are supported."}

        if not any(mime.startswith(p.replace("image/", "image/")) for p in self.ALLOWED_MIME_PREFIXES):
            return {"error": f"Unsupported mime type: {mime}"}

        with open(real_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        data_url = f"data:{mime};base64,{b64}"
        content = []
        if text:
            content.append({"type": "text", "text": text})
        content.append({"type": "image_url", "image_url": {"url": data_url}})

        return {"attach_user_message": content}
