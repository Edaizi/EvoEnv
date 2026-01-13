from loguru import logger

from virtual_server.docker_sandbox import DockerSandbox

class ExecuteCommand:
    """A tool to execute shell commands in a Docker sandbox."""
    MAX_DISPLAY_LEN = 10240

    def __init__(self, docker_sandbox: DockerSandbox):
        """
        Initializes the ExecuteCommand tool.

        Args:
            sandbox: An instance of DockerSandbox where commands will be executed.
        """
        self.sandbox = docker_sandbox

    def _truncate(self, value) -> str:
        """
        Truncates the given value to MAX_DISPLAY_LEN characters if necessary.
        Appends a note about the original total length when truncation occurs.
        """
        s = "" if value is None else str(value)
        real_length = len(s)
        if real_length > self.MAX_DISPLAY_LEN:
            return s[:self.MAX_DISPLAY_LEN] + (
                f"...(output total length {real_length} characters, display 1000 characters)"
            )
        return s

    def __call__(self, command: str) -> str:
        """
        Executes a shell command within a secure, isolated Docker sandbox environment. You can use almost all the command in a linux operation system, like: view files in your workspace: `ls -al .`; generate a new file: `touch example.py`; write something to a file: `echo "print('hello world')" > example.py`; run a script: `python example.py`. 
        
        Args:
            command: The shell command to be executed in the sandbox. Must be a non-empty string.
        """
        if not command or not isinstance(command, str):
            logger.error("Agent outputs an empty command.")
            return "Error: Command must be a non-empty string."
            
        try:
            exit_code, output = self.sandbox.run_command(command)
            
            # Truncate exit_code and output separately if they exceed 1000 chars
            exit_code_str = self._truncate(exit_code)
            output_str = self._truncate(output)
            
            formatted_output = f"Exit Code: {exit_code_str}\nOutput:\n{output_str}"
            # logger.info(formatted_output)
            return formatted_output
        except Exception as e:
            logger.error(f"An error occurred while executing the command: {str(e)}")
            return f"An error occurred while executing the command: {str(e)}"

