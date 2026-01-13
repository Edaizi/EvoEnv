import os
import shutil
from loguru import logger
from pathlib import Path

from virtual_server.registry import register_server
from virtual_server.base_server import BaseServer


@register_server(server_name='cloud_disk')
class CloudDisk(BaseServer):
    def __init__(self, task_root_path: str, *args, **kwargs) -> None:
        cloud_disk_root_path = os.path.join(task_root_path, 'cloud_disk')
        workspace_path = os.path.join(task_root_path, 'workspace')
        self.root_path = Path(cloud_disk_root_path)
        self.workspace_path = Path(workspace_path)

        self.root_path.mkdir(parents=True, exist_ok=True)
        self.workspace_path.mkdir(parents=True, exist_ok=True)

    def log_and_return_message(self, message: str):
        logger.info(message)
        return message

    def download_file(self, file_path: str, target_path: str):
        source_real_path = self.root_path / file_path
        if not source_real_path.exists():
            error_message = f"Error: Source file '{source_real_path}' does not exist."
            self.log_and_return_message(error_message)
        if not source_real_path.is_file():
            error_message = f"Error: Source path '{source_real_path}' is a directory, not a file."
            self.log_and_return_message(error_message)
        
        target_real_path = self.workspace_path / target_path
        final_destination_path = None
        try:
            is_target_intended_as_dir = target_path.endswith(os.sep)
            if target_real_path.is_dir():
                final_destination_path = target_real_path / source_real_path.name
                logger.debug(f"Target '{target_real_path}' is an existing directory. Saving file inside it.")
            
            elif is_target_intended_as_dir:
                target_real_path.mkdir(parents=True, exist_ok=True)
                final_destination_path = target_real_path / source_real_path.name
                logger.debug(f"Target '{target_path}' is intended as a directory. Creating it and saving file inside.")
            else:
                target_real_path.parent.mkdir(parents=True, exist_ok=True)
                final_destination_path = target_real_path
                logger.debug(f"Target '{target_real_path}' is a file path. Saving file to this location.")
            shutil.copy2(source_real_path, final_destination_path)
            
            success_message = f"Successfully downloaded '{file_path}' to '{target_path}'"
            self.log_and_return_message(success_message)
        except Exception as e:
            error_message = f"An error occurred during download: {e}"
            self.log_and_return_message(error_message)

    def open_folder(self, folder_path: str):
        real_folder_path = self.root_path / folder_path
        if not os.path.isdir(real_folder_path):
            erro_message = f'Error: {folder_path} is not a directory. can not open it.'
            self.log_and_return_message(erro_message)
        
        if not os.path.exists(real_folder_path):
            erro_message = f'Error: {folder_path} does not exist.'
            self.log_and_return_message(erro_message)

        outputs = []
        for item in os.listdir(real_folder_path):
            item_path = real_folder_path / item
            if item_path.is_dir():
                outputs.append(f'{item}/')
            else:
                outputs.append(item)

        output_str = '\n'.join(outputs)
        logger.info(f"[List Folder] Contents of '{folder_path}': \n{output_str}")
        return output_str
    
    def close(self):
        return


if __name__ == '__main__':
    pass