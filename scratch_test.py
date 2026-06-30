import sys
import os

# Append the project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    print("Testing imports...")
    from llm.model import get_gemini
    print("[OK] llm.model imported successfully.")
    
    from graph.state import AgentState
    print("[OK] graph.state imported successfully.")
    
    from graph.agent_response import AgentResponse
    print("[OK] graph.agent_response imported successfully.")
    
    from graph.utils import generate_booking_pdf, count_request
    print("[OK] graph.utils imported successfully.")
    
    from graph.prompt_service.lab_data import LabDataService
    print("[OK] graph.prompt_service.lab_data imported successfully.")
    
    from graph.schemas.booking_schema import BookingResponse
    from graph.schemas.complaint_schema import ComplaintResponse
    from graph.schemas.inquiry_schema import InquiryResponse
    print("[OK] graph.schemas imported successfully.")
    
    from graph.nodes.booking_node import booking_node
    from graph.nodes.complaint_node import complaint_node
    from graph.nodes.intent_node import intent_node
    from graph.nodes.inquiry_node import inquiry_node
    from graph.nodes.direct_node import direct_node
    print("[OK] graph.nodes imported successfully.")
    
    from graph.agent_graph import get_agent_graph
    print("[OK] graph.agent_graph imported successfully.")
    
    # Try compilation
    g = get_agent_graph()
    print("[OK] Graph compiled successfully.")
    print("All checks passed successfully!")
except Exception as e:
    print(f"[FAIL] Check failed: {e}")
    sys.exit(1)
