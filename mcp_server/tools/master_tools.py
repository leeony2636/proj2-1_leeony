from mcp_server.adapters.local_runtime import LocalRuntime
runtime=LocalRuntime()
def request_game_master(session_id:str,team_id:str,reason:str)->dict: return runtime.request_game_master(session_id,team_id,reason)
def report_equipment_issue(session_id:str,team_id:str,detail:str)->dict: return runtime.request_game_master(session_id,team_id,f"EQUIPMENT_ISSUE:{detail}")
def get_master_requests()->list[dict]: return runtime.get_master_requests()
