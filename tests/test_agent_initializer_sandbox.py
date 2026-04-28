import sys
import os
import tempfile
from unittest.mock import MagicMock, patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_bash_tool_gets_sandbox_when_enabled():
    from bridge.agent_initializer import AgentInitializer
    from agent.tools.tool_manager import ToolManager

    mock_bridge = MagicMock()
    mock_agent_bridge = MagicMock()
    mock_agent_bridge.scheduler_initialized = False
    mock_agent_bridge.create_agent.return_value = MagicMock()

    init = AgentInitializer(mock_bridge, mock_agent_bridge)

    with tempfile.TemporaryDirectory() as tmp:
        sandbox = os.path.join(tmp, "metaclaw-sandbox")
        workspace = os.path.join(tmp, "metaclaw")
        os.makedirs(workspace, exist_ok=True)

        with patch('config.conf') as mock_conf, \
             patch('bridge.agent_initializer.expand_path', side_effect=lambda p: os.path.expanduser(p)), \
             patch('bridge.agent_initializer.DEFAULT_AGENT_WORKSPACE', workspace):

            mock_conf.return_value.get.side_effect = lambda key, default=None: {
                "agent_workspace": workspace,
                "sandbox_enabled": True,
                "sandbox_workspace": sandbox,
                "agent_max_steps": 20,
                "agent_max_context_tokens": 50000,
                "conversation_persistence": False,
            }.get(key, default)

            mock_bash = MagicMock()
            mock_bash.name = "bash"
            mock_bash.config = None
            mock_bash.cwd = "/old"

            mock_read = MagicMock()
            mock_read.name = "read"
            mock_read.config = None
            mock_read.cwd = "/old"

            # Patch the singleton _instance so ToolManager() returns our mock
            with patch.object(ToolManager, '_instance', mock_tm := MagicMock()):
                mock_tm.tool_classes = {"bash": MagicMock, "read": MagicMock}
                def create_tool(name):
                    return mock_bash if name == "bash" else mock_read
                mock_tm.create_tool = create_tool

                with patch.object(init, '_setup_memory_system', return_value=(None, [])), \
                     patch.object(init, '_initialize_scheduler'), \
                     patch.object(init, '_initialize_skill_manager', return_value=None), \
                     patch('agent.prompt.load_context_files', return_value={}), \
                     patch('agent.prompt.PromptBuilder') as MockPB:
                    MockPB.return_value.build.return_value = "system"
                    agent = init.initialize_agent()

            assert mock_bash.cwd == sandbox, f"Expected bash cwd={sandbox}, got {mock_bash.cwd}"
            assert mock_read.cwd == workspace, f"Expected read cwd={workspace}, got {mock_read.cwd}"
            assert os.path.exists(sandbox), "Sandbox directory should be created"
