import docker
import os
import shortuuid
import platform
from loguru import logger

from virtual_server.registry import register_server
from virtual_server.base_server import BaseServer


def is_wsl():
    return 'windows' in platform.uname().system.lower()


@register_server(server_name='docker_sandbox')
class DockerSandbox(BaseServer):
    """
    A highly isolated sandbox environment built and run via a Dockerfile.
    Upon initialization, this class checks if the specified image tag exists.
    If not, it automatically builds the image from the given Dockerfile.
    Subsequently, it starts a container that:
    - Has network access completely disabled.
    - Has a read-only root filesystem.
    - Only mounts the specified local workspace directory as read-write.
    It is recommended to use a 'with' statement to manage sandbox instances,
    ensuring proper cleanup of container resources.
    Example:
        # Assuming the Dockerfile is in the "./" directory
        with DockerSandbox(
            dockerfile_path="./Dockerfile",
            image_tag="python-sqlite-sandbox:latest",
            workspace_dir="./my_workspace"
        ) as sandbox:
            exit_code, output = sandbox.run_command("sqlite3 --version")
            print(output)
    """
    def __init__(
        self,
        task_root_path: str,
        dockerfile_path: str = 'virtual_server/Dockerfile',
        image_tag: str = 'my-env:3.0',
        mem_limit: str = "256m",
        pids_limit: int = 100,
        cpu_shares: int = 512,
        *args, **kwargs
    ):
        """
        Initializes the Docker sandbox.
        :param workspace_dir: The local host path to mount into the container at /workspace.
        :param dockerfile_path: The path to the Dockerfile used for building the image.
        :param image_tag: The tag for the image to build or use (e.g., "my-image:latest").
        :param mem_limit: Memory limit for the container (e.g., "256m", "1g").
        :param pids_limit: Maximum number of processes allowed in the container.
        :param cpu_shares: Relative weight for CPU resources.
        """
        self._session_id = shortuuid.uuid()
        self.image_tag = image_tag
        self.client = docker.from_env()
        self.container = None
        # Resource limits
        self.resource_limits = {
            "mem_limit": mem_limit,
            "pids_limit": pids_limit,
            "cpu_shares": cpu_shares,
        }
        # Set up the workspace
        workspace_dir = os.path.join(task_root_path, 'workspace')
        self.host_workspace = os.path.abspath(workspace_dir)
        os.makedirs(self.host_workspace, exist_ok=True)
        try:
            # 1. Build the image from Dockerfile if it does not exist
            self._build_image_if_needed(dockerfile_path)
            # 2. Start the container
            self._start_container()
        except Exception as e:
            logger.error(f"Sandbox environment setup failed: {e}")
            self.close()  # Attempt to clean up on startup failure
            raise

    def _build_image_if_needed(self, dockerfile_path: str):
        """Checks if the image exists, and builds it from the Dockerfile if not."""
        try:
            self.client.images.get(self.image_tag)
            logger.info(f"Image '{self.image_tag}' already exists, skipping build.")
        except docker.errors.ImageNotFound:
            logger.info(f"Image '{self.image_tag}' not found, starting build...")
            dockerfile_dir = os.path.dirname(os.path.abspath(dockerfile_path))
            dockerfile_name = os.path.basename(dockerfile_path)
            try:
                image, build_log = self.client.images.build(
                    path=dockerfile_dir,
                    dockerfile=dockerfile_name,
                    tag=self.image_tag,
                    rm=True # Remove intermediate containers after a successful build
                )
                logger.success(f"Image '{self.image_tag}' built successfully.")
                # for line in build_log:
                #     if 'stream' in line:
                #         print(line['stream'].strip())
            except docker.errors.BuildError as e:
                logger.error(f"Image build failed: {e}")
                for line in e.build_log:
                    if 'stream' in line:
                        logger.error(line['stream'].strip())
                raise

    def _start_container(self):
        """Starts the container in a highly isolated mode."""
        logger.info("Starting a network-isolated container...")
        self.container = self.client.containers.run(
            self.image_tag,
            command="sleep infinity",  # Keep the container running
            detach=True,
            # Security settings
            network_disabled=True,     # Disable networking
            read_only=True,            # Make root filesystem read-only
            security_opt=["no-new-privileges"],
            cap_drop=['ALL'],
            # Mount workspace as read-write
            volumes={self.host_workspace: {'bind': '/workspace', 'mode': 'rw'}},
            # Run as a non-root user
            user="root" if is_wsl() else f"{os.getuid()}:{os.getgid()}",
            **self.resource_limits
        )
        logger.success(f"Container {self.container.short_id} started successfully.")

    def run_command(self, command: str) -> tuple[int, str]:
        """Executes a command inside the container's workspace."""
        if not self.container:
            raise RuntimeError("Container is not running.")
        # logger.info(f"\n> Executing command: '{command}'")
        exec_result = self.container.exec_run(
            ["/bin/sh", "-c", command],
            workdir="/workspace",  # Execute inside the mounted workspace
            demux=True
        )
        exit_code = exec_result.exit_code
        stdout_bytes, stderr_bytes = exec_result.output
        output = ""
        if stdout_bytes:
            output += stdout_bytes.decode('utf-8', errors='ignore')
        if stderr_bytes:
            output += stderr_bytes.decode('utf-8', errors='ignore')
        # logger.info(f"Exit code: {exit_code}")
        # logger.info(f"Output:\n{output.strip()}")
        return exit_code, output.strip()
    
    def close(self):
        """Stops and removes the container, cleaning up resources."""
        if self.container:
            logger.info("Cleaning up sandbox resources...")
            try:
                self.container.stop(timeout=5)
                self.container.remove()
                logger.success("Sandbox cleaned up successfully.")
            except docker.errors.NotFound:
                pass # Container might have already been removed
            except Exception as e:
                logger.error(f"Error cleaning up container {self.container.short_id}: {e}")
            finally:
                self.container = None

    def __enter__(self): 
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb): 
        self.close()

# --- Example Usage ---
if __name__ == '__main__':
    # Define workspace directory and Dockerfile path
    WORKSPACE_DIR = "./sandbox_workspace"
    DOCKERFILE = "./Dockerfile"
    IMAGE_TAG = "my-env:2.0"

    print("--- First Run ---")
    # On the first run, it will detect that the image does not exist and build it.
    with DockerSandbox(
        workspace_dir=WORKSPACE_DIR,
        dockerfile_path=DOCKERFILE,
        image_tag=IMAGE_TAG
    ) as sandbox:
        print("\n[Test 1] Check sqlite3 version")
        sandbox.run_command("sqlite3 --version")
        print(sandbox.run_command('touch readme.md'))
        
        print("\n[Test 2] Create and operate on a database")
        sandbox.run_command('sqlite3 test.db "CREATE TABLE stocks (date text, trans text, symbol text, qty real, price real);"')
        sandbox.run_command('sqlite3 test.db "INSERT INTO stocks VALUES (\'2024-05-21\',\'BUY\',\'MSFT\',100,320.34);"')

        print("\n[Test 3] Query the database content")
        exit_code, output = sandbox.run_command('sqlite3 test.db "SELECT * FROM stocks;"')
        assert "MSFT" in output
        
        print("\n[Test 4] Check workspace files")
        exit_code, output = sandbox.run_command('ls -l')
        assert "test.db" in output
        
    print("\n--- Second Run ---")
    # On the second run, it will find the existing image and skip the build, starting up faster.
    with DockerSandbox(
        workspace_dir=WORKSPACE_DIR,
        dockerfile_path=DOCKERFILE,
        image_tag=IMAGE_TAG
    ) as sandbox:
        print("\n[Test 5] Verify the database file from the previous run still exists")
        exit_code, output = sandbox.run_command('sqlite3 test.db "SELECT * FROM stocks;"')
        assert "MSFT" in output
        print("Tests successful!")