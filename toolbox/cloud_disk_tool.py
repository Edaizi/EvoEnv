from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from virtual_server.cloud_disk import CloudDisk

from loguru import logger


class DownloadFileFromCloudDisk:
    def __init__(self, cloud_disk: "CloudDisk"):
        self.cloud_disk = cloud_disk
    def __call__(self, file_path: str, target_path: str) -> str:
        """
        Download a file from the cloud disk to the local workspace.

        Args:
            file_path: The path of the file on the cloud disk. This must be a relative path from the cloud disk\'s root directory. For example: `manuals.txt` or `financial/approval/T24I.txt`. Do not include prefixes like `CloudDisk:` or `CloudDisk://`.
            target_path: The destination path in the local workspace where the file will be saved, like `manuals.txt`, `approval/T23I.txt`. Can be a directory or a file path. Must be a non-empty string.

        Returns:
            A string indicating the result of the download operation (success or error message).
        """
        try:
            response = self.cloud_disk.download_file(
                file_path=file_path,
                target_path=target_path
            )
            # logger.info(f'[DownloadFileFromCloudDisk] {response}')
            return response
        except Exception as e:
            # logger.info(f'[DownloadFileFromCloudDisk] An unexpected error occurred while trying to download the file: {str(e)}')
            return f"An unexpected error occurred while trying to download the file: {str(e)}"
        

class OpenFolderInCloudDisk:
    def __init__(self, cloud_disk: "CloudDisk"):
        self.cloud_disk = cloud_disk
    def __call__(self, folder_path: str) -> str:
        """
        List the contents of a specified folder on the cloud disk.

        Args:
            folder_path: The path of the folder on the cloud disk to be opened/listed. like `financial/approval`, `financial/`. Must be a non-empty string. **Use `./` to view files and folders in the root directory**. Do not include prefixes like `CloudDisk:` or `CloudDisk://`.
            
        Returns:
            A string containing the space-separated names of files and subdirectories in the folder. Directories are appended with a '/'. Returns an error message if the path is invalid or does not exist.
        """
        try:
            response = self.cloud_disk.open_folder(folder_path=folder_path)
            # logger.info(f'[OpenFolderInCloudDisk]\n{response}')
            return response
        except Exception as e:
            # logger.info(f'[DownloadFileFromCloudDisk] An unexpected error occurred while trying to download the file: {str(e)}')
            return f"An unexpected error occurred while trying to open the folder: {str(e)}"