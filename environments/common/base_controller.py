"""
Base Event Controller for managing different interaction patterns across benchmarks.

The Event Controller is responsible for:
1. Managing the flow of events in the environment
2. Deciding when and how to inject new events (e.g., incoming emails, new tasks)
3. Maintaining the state of the narrative/story progression
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from loguru import logger


class BaseController(ABC):
    """
    Abstract base class for event controllers.
    
    Different benchmarks may require different event management strategies:
    - Reactive: Only responds to agent actions (TraineeBench)
    - Narrative: Proactively pushes story events based on triggers (GAIA2)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the event controller.
        
        Args:
            config: Configuration dictionary containing controller-specific settings
        """
        self.config = config
        self.turn_count = 0
        self.state = {}
    
    @abstractmethod
    def update(
        self, 
        agent_action: Optional[Any] = None,
        action_result: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Update the controller state and generate new events if needed.
        
        Args:
            agent_action: The action taken by the agent (e.g., tool call)
            action_result: The result of executing the action
            
        Returns:
            List of new events to be injected into the observation.
            Each event is a dict with 'role' and 'content' keys.
        """
        pass
    
    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """
        Get the current state of the controller.
        
        Returns:
            Dictionary containing controller state information
        """
        pass
    
    def increment_turn(self):
        """Increment the turn counter."""
        self.turn_count += 1


class ReactiveController(BaseController):
    """
    Reactive controller for benchmarks like TraineeBench.
    
    This controller does NOT generate additional events. It only responds
    to agent actions without injecting narrative elements.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        logger.info("Initialized ReactiveController (no proactive events)")
    
    def update(
        self,
        agent_action: Optional[Any] = None,
        action_result: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        For reactive mode, no additional events are generated.
        
        Returns:
            Empty list (no new events)
        """
        self.increment_turn()
        return []
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current state of the reactive controller.
        
        Returns:
            Dictionary with turn count and mode
        """
        return {
            "mode": "reactive",
            "turn_count": self.turn_count
        }


# TODO: To be really implemented
class NarrativeController(BaseController):
    """
    Narrative controller for benchmarks like GAIA2.
    
    This controller maintains an event graph (DAG) and proactively pushes
    story events when certain conditions are met (e.g., turn count, specific actions).
    
    Event Graph Structure:
    {
        "event_id": {
            "type": "email" | "task" | "notification",
            "content": "...",
            "triggers": {
                "turn": 5,  # Trigger after turn 5
                "action": "read_email",  # Trigger when specific action occurs
                "dependencies": ["event_1", "event_2"]  # Require other events first
            },
            "status": "pending" | "unlocked" | "delivered"
        }
    }
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Load event graph from config
        self.event_graph: Dict[str, Dict] = config.get('event_graph', {})
        
        # Track which events have been delivered
        self.delivered_events = set()
        
        # Track which events are unlocked (ready to deliver)
        self.unlocked_events = set()
        
        # Initialize all events as pending
        for event_id in self.event_graph:
            self.event_graph[event_id]['status'] = 'pending'
        
        logger.info(f"Initialized NarrativeController with {len(self.event_graph)} events")
    
    def update(
        self,
        agent_action: Optional[Any] = None,
        action_result: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Check for triggered events and return them.
        
        Args:
            agent_action: The action taken by the agent (e.g., tool call object)
            action_result: Result of the action execution
            
        Returns:
            List of new events to inject into the agent's observation
        """
        self.increment_turn()
        
        new_events = []
        
        # Extract action name if available
        action_name = None
        if agent_action and hasattr(agent_action, 'function'):
            action_name = agent_action.function.name
        
        # Check each pending event for triggers
        for event_id, event_data in self.event_graph.items():
            if event_data['status'] != 'pending':
                continue
            
            triggers = event_data.get('triggers', {})
            
            # Check turn-based trigger
            if 'turn' in triggers and self.turn_count >= triggers['turn']:
                if self._check_dependencies(event_id):
                    self._unlock_event(event_id)
            
            # Check action-based trigger
            if 'action' in triggers and action_name == triggers['action']:
                if self._check_dependencies(event_id):
                    self._unlock_event(event_id)
        
        # Deliver all unlocked events
        for event_id in list(self.unlocked_events):
            event_message = self._deliver_event(event_id)
            if event_message:
                new_events.append(event_message)
        
        if new_events:
            logger.info(f"NarrativeController: Injected {len(new_events)} new event(s) at turn {self.turn_count}")
        
        return new_events
    
    def _check_dependencies(self, event_id: str) -> bool:
        """
        Check if all dependency events have been delivered.
        
        Args:
            event_id: ID of the event to check
            
        Returns:
            True if all dependencies are met
        """
        triggers = self.event_graph[event_id].get('triggers', {})
        dependencies = triggers.get('dependencies', [])
        
        for dep_id in dependencies:
            if dep_id not in self.delivered_events:
                return False
        
        return True
    
    def _unlock_event(self, event_id: str):
        """
        Mark an event as unlocked (ready to deliver).
        
        Args:
            event_id: ID of the event to unlock
        """
        self.event_graph[event_id]['status'] = 'unlocked'
        self.unlocked_events.add(event_id)
        logger.debug(f"Event '{event_id}' unlocked")
    
    def _deliver_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Deliver an unlocked event and mark it as delivered.
        
        Args:
            event_id: ID of the event to deliver
            
        Returns:
            Event message dict with 'role' and 'content', or None if event not found
        """
        if event_id not in self.event_graph:
            return None
        
        event_data = self.event_graph[event_id]
        event_type = event_data.get('type', 'notification')
        content = event_data.get('content', '')
        
        # Mark as delivered
        self.event_graph[event_id]['status'] = 'delivered'
        self.delivered_events.add(event_id)
        self.unlocked_events.discard(event_id)
        
        # Format the message based on event type
        if event_type == 'email':
            message_content = f"[New Email Received]\n{content}"
        elif event_type == 'task':
            message_content = f"[New Task Assigned]\n{content}"
        else:
            message_content = f"[System Notification]\n{content}"
        
        logger.info(f"Delivered event '{event_id}' ({event_type})")
        
        return {
            'role': 'system',
            'content': message_content
        }
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current state of the narrative controller.
        
        Returns:
            Dictionary with detailed controller state
        """
        return {
            "mode": "narrative",
            "turn_count": self.turn_count,
            "total_events": len(self.event_graph),
            "delivered_events": len(self.delivered_events),
            "unlocked_events": len(self.unlocked_events),
            "pending_events": len([e for e in self.event_graph.values() if e['status'] == 'pending'])
        }
