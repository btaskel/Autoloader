import hashlib
import io
import json
import os.path
import time
import urllib.parse
import urllib.request
import uuid
from typing import List, Dict

import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
from PIL import Image

from src import log
from src.config import config

server_address = "127.0.0.1:7860"
client_id = str(uuid.uuid4())


class Comfyui:
    def __init__(self):
        self.ws = websocket.WebSocket()
        try:
            self.ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
        except ConnectionRefusedError as e:
            log.fatal(f"连接comfyui失败，可能是因为没有启动造成的: {e}")

    def close(self):
        if self.ws and self.ws.connected:
            self.ws.close()
            log.info("WebSocket closed.")

    @staticmethod
    def saveRecord(jsonFile: str):
        with open(config.record_path, mode="w+", encoding="utf-8") as _f:
            json.dump(json.loads(jsonFile), _f, ensure_ascii=False, indent=4)

    def send(self, workflow: str, savePath: str) -> (List[str], Dict[str, List[dict]]):
        self.saveRecord(workflow)

        images, outputs = self.get_images(json.loads(workflow))

        outputList: list[str] = []
        for node_id in images:
            for image_data in images[node_id]:
                hasher = hashlib.sha256()
                hasher.update(image_data)
                tic = int(time.time() * 1000)
                filename_base = f"{tic}-{hasher.hexdigest()}"
                path = os.path.join(savePath, f"{filename_base}.jpg")

                try:
                    img = Image.open(io.BytesIO(image_data))
                    if img.mode == 'RGBA' or img.mode == 'P':
                        img = img.convert('RGB')
                    elif img.mode != 'RGB' and img.mode != 'L':  # L is grayscale, also supported by JPG
                        log.warn(
                            f"Image {filename_base} has mode {img.mode}, attempting to save as JPG. May cause issues if not RGB/L.")
                    img.save(path, format='JPEG', quality=95)  # Adjust quality (0-100) as needed
                    outputList.append(path)

                except Exception as e:
                    log.error(f"Failed to process and save image {filename_base}.jpg: {e}")
                    # Optionally save the raw data as PNG for debugging
                    # fallback_path = os.path.join(savePath, f"{filename_base}_error.png")
                    # try:
                    #     with open(fallback_path, mode="wb") as f_err:
                    #         f_err.write(image_data)
                    #     log.warn(f"Saved raw image data to {fallback_path} due to conversion error.")
                    # except IOError as io_err:
                    #     log.error(f"Failed to save fallback PNG {fallback_path}: {io_err}")

        return outputList, outputs

    @staticmethod
    def queue_prompt(prompt):
        p = {"prompt": prompt, "client_id": client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request("http://{}/prompt".format(server_address), data=data)
        return json.loads(urllib.request.urlopen(req).read())

    @staticmethod
    def get_image(filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
            return response.read()

    @staticmethod
    def get_history(prompt_id):
        with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
            return json.loads(response.read())

    def get_images(self, prompt)->(dict,dict):
        prompt_id = self.queue_prompt(prompt)['prompt_id']
        output_images = {}
        while True:
            out = self.ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break  # Execution is done
            else:
                continue

        history = self.get_history(prompt_id)[prompt_id]

        with open(config.record_comfyui_outputs_path, mode="w+", encoding="utf-8") as f:
            f.write(json.dumps(history))

        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            images_output = []
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = self.get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
            output_images[node_id] = images_output
        return output_images, history['outputs']