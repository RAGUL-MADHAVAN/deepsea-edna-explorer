
import subprocess
import shutil
import logging
import os
from pathlib import Path

logger = logging.getLogger('DeepSeaEDNA.tools')

class ExternalTool:
    """
    Base class for wrapping external bioinformatics tools.
    """
    def __init__(self, tool_name, mandatory=True):
        self.tool_name = tool_name
        self.mandatory = mandatory
        self.executable = shutil.which(tool_name)
        
        if not self.executable and mandatory:
            logger.warning(f"Mandatory tool '{tool_name}' not found in PATH.")
        elif not self.executable:
            logger.info(f"Optional tool '{tool_name}' not found.")
            
    def is_available(self):
        return self.executable is not None
        
    def run(self, args, output_file=None, capture_output=True):
        """
        Run the external tool with the provided arguments.
        """
        if not self.is_available():
            if self.mandatory:
                raise RuntimeError(f"Cannot run {self.tool_name}: tool not found.")
            else:
                logger.warning(f"Skipping {self.tool_name} (not found).")
                return None
                
        cmd = [self.executable] + [str(a) for a in args]
        logger.info(f"Running command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                check=True
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Tool {self.tool_name} failed with exit code {e.returncode}")
            logger.error(f"STDERR: {e.stderr}")
            raise RuntimeError(f"Tool {self.tool_name} failed: {e.stderr}")

    def run_custom(self, tool_name, args, capture_output=True):
        """
        Run a related executable that is not the primary tool_name.

        Example: bowtie2 wrapper also needs bowtie2-build.
        """
        executable = shutil.which(tool_name)
        if not executable:
            if self.mandatory:
                raise RuntimeError(f"Cannot run {tool_name}: tool not found.")
            logger.warning(f"Skipping {tool_name} (not found).")
            return None

        cmd = [executable] + [str(a) for a in args]
        logger.info(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                check=True
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Tool {tool_name} failed with exit code {e.returncode}")
            logger.error(f"STDERR: {e.stderr}")
            raise RuntimeError(f"Tool {tool_name} failed: {e.stderr}")

def check_dependencies(tools_list):
    """
    Check if a list of tools are available.
    Returns a dict of tool_name -> available (bool)
    """
    status = {}
    for tool in tools_list:
        status[tool] = shutil.which(tool) is not None
    return status
