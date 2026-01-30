"""
Test script for Event Controller functionality.

This script demonstrates:
1. ReactiveController (no proactive events)
2. NarrativeController (with event graph and triggers)
"""

import json
from environments.common import ReactiveController, NarrativeController


def test_reactive_controller():
    """Test the ReactiveController - should not generate any events."""
    print("\n" + "="*60)
    print("Testing ReactiveController")
    print("="*60)
    
    controller = ReactiveController(config={})
    
    # Simulate multiple turns
    for i in range(5):
        events = controller.update()
        print(f"Turn {i+1}: Generated {len(events)} events")
        print(f"State: {controller.get_state()}")
    
    assert controller.turn_count == 5
    print("\n✓ ReactiveController test passed!")


def test_narrative_controller():
    """Test the NarrativeController with event graph."""
    print("\n" + "="*60)
    print("Testing NarrativeController")
    print("="*60)
    
    # Load example configuration
    with open('environments/common/controller_config_example.json', 'r') as f:
        config_examples = json.load(f)
    
    controller_config = config_examples['narrative_controller_example']['controller_config']
    controller = NarrativeController(controller_config)
    
    print(f"\nInitial state: {controller.get_state()}")
    
    # Simulate turns
    print("\n--- Simulating Turn-based Triggers ---")
    for i in range(12):
        # Create a mock action object
        class MockAction:
            class Function:
                name = "check_email" if i == 4 else "other_action"
            function = Function()
        
        action = MockAction() if i == 4 else None
        events = controller.update(agent_action=action)
        
        if events:
            print(f"\nTurn {i+1}: {len(events)} event(s) triggered!")
            for event in events:
                print(f"  Role: {event['role']}")
                print(f"  Content: {event['content'][:80]}...")
        else:
            print(f"Turn {i+1}: No new events")
        
        print(f"  State: {controller.get_state()}")
    
    # Verify final state
    final_state = controller.get_state()
    assert final_state['turn_count'] == 12
    assert final_state['delivered_events'] > 0
    
    print("\n✓ NarrativeController test passed!")


def test_action_based_trigger():
    """Test action-based event triggering."""
    print("\n" + "="*60)
    print("Testing Action-Based Triggers")
    print("="*60)
    
    config = {
        "event_graph": {
            "action_event": {
                "type": "email",
                "content": "This event is triggered by reading an email",
                "triggers": {
                    "action": "read_email"
                }
            }
        }
    }
    
    controller = NarrativeController(config)
    
    # First few turns with different actions
    class MockAction:
        class Function:
            def __init__(self, name):
                self.name = name
        def __init__(self, name):
            self.function = self.Function(name)
    
    # Try wrong action
    events = controller.update(agent_action=MockAction("write_file"))
    print(f"Turn 1 (write_file): {len(events)} events")
    
    # Try correct action
    events = controller.update(agent_action=MockAction("read_email"))
    print(f"Turn 2 (read_email): {len(events)} events triggered!")
    
    if events:
        print(f"  Event content: {events[0]['content']}")
    
    assert len(events) > 0, "Action-based trigger failed!"
    print("\n✓ Action-based trigger test passed!")


def test_dependency_chain():
    """Test event dependencies."""
    print("\n" + "="*60)
    print("Testing Event Dependencies")
    print("="*60)
    
    config = {
        "event_graph": {
            "event_1": {
                "type": "notification",
                "content": "First event",
                "triggers": {
                    "turn": 1
                }
            },
            "event_2": {
                "type": "notification",
                "content": "Second event (depends on event_1)",
                "triggers": {
                    "turn": 2,
                    "dependencies": ["event_1"]
                }
            },
            "event_3": {
                "type": "notification",
                "content": "Third event (depends on both)",
                "triggers": {
                    "turn": 3,
                    "dependencies": ["event_1", "event_2"]
                }
            }
        }
    }
    
    controller = NarrativeController(config)
    
    for i in range(5):
        events = controller.update()
        print(f"Turn {i+1}: {len(events)} event(s)")
        for event in events:
            print(f"  - {event['content']}")
    
    final_state = controller.get_state()
    assert final_state['delivered_events'] == 3, "Not all events were delivered!"
    print("\n✓ Dependency chain test passed!")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Event Controller Test Suite")
    print("="*60)
    
    try:
        test_reactive_controller()
        test_narrative_controller()
        test_action_based_trigger()
        test_dependency_chain()
        
        print("\n" + "="*60)
        print("✓ All tests passed!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
