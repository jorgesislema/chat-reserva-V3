"""
Simple test for the hours skill.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from skills.operations.hours_skill import HoursSkill

def test_hours_skill():
    """Test the hours skill."""
    # Create skill instance
    skill = HoursSkill({})
    
    # Initialize
    assert skill.initialize() == True, "Hours skill should initialize successfully"
    assert skill._is_initialized == True, "Skill should be marked as initialized"
    
    # Get capabilities
    capabilities = skill.get_capabilities()
    assert "get_hours" in capabilities, "Should have get_hours capability"
    
    # Execute get_hours action
    result = skill.execute("get_hours")
    assert isinstance(result, str), "Result should be a string"
    assert "HORARIOS DE ATENCION" in result, "Should contain clinic hours header"
    assert "Lunes a Viernes: 08:00 a 18:00" in result, "Should contain weekday hours"
    assert "Sabados y Domingos: CERRADO" in result, "Should indicate weekends closed"
    
    # Test health check
    health = skill.health_check()
    assert health["status"] == "healthy", "Skill should report healthy status"
    assert health["skill"] == "HoursSkill", "Should report correct skill name"
    assert "get_hours" in health["capabilities"], "Should list capabilities"
    
    print("[PASS] Hours skill test passed!")
    return True

if __name__ == "__main__":
    try:
        test_hours_skill()
        print("All tests passed!")
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        sys.exit(1)