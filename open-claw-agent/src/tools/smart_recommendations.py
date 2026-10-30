"""
Smart recommendations engine for OpenClaw.
Suggests places, events, breaks, meeting recommendations, etc.
"""

from datetime import datetime, timedelta
from typing import Optional


def get_calendar_recommendations(events: list[dict]) -> list[str]:
    """Analyze calendar and suggest what to do during breaks/before events."""
    if not events:
        return ["📅 No upcoming events. You could: 1) Work on projects 2) Take a break 3) Go for a walk"]
    
    recommendations = []
    now = datetime.now()
    
    for i, event in enumerate(events):
        start_str = event.get("start", {}).get("dateTime", "")
        if not start_str:
            continue
        
        try:
            event_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            title = event.get("summary", "Event")
            
            # Calculate time until event
            time_until = event_start - now
            hours_until = time_until.total_seconds() / 3600
            
            if 0 <= hours_until <= 2:
                recommendations.append(f"🔔 {title} starts in ~{int(hours_until)} hour(s) - prepare!")
            elif hours_until > 2 and hours_until <= 4:
                recommendations.append(f"⏰ Heads up: {title} in {int(hours_until)} hours - consider breaking soon")
            elif i == 0:  # First event
                recommendations.append(f"📌 Next: {title} at {event_start.strftime('%H:%M')}")
        except:
            pass
    
    return recommendations if recommendations else ["📅 Your schedule looks good"]


def suggest_break_locations() -> list[str]:
    """Suggest places to take a break based on time of day."""
    hour = datetime.now().hour
    
    if 7 <= hour < 12:
        return [
            "☕ Morning break? Try a local cafe for fresh coffee",
            "🚶 Take a 10-min walk to wake up",
            "🥤 Grab water and stretch - stay hydrated",
        ]
    elif 12 <= hour < 14:
        return [
            "🍽 Lunch time! Check local restaurants",
            "🥗 Quick salad or sandwich nearby",
            "🏪 Cafeteria for a quick meal",
        ]
    elif 14 <= hour < 17:
        return [
            "☕ Afternoon slump? Get some coffee",
            "🚶 Walk around the block to refresh",
            "🧘 Meditation break for 5 minutes",
        ]
    elif 17 <= hour < 20:
        return [
            "🍴 Dinner time approaches",
            "🏃 Go for an evening run",
            "🌳 Evening walk in the park",
        ]
    else:
        return [
            "🌙 Late night? Consider sleep soon",
            "🎮 Quick gaming break?",
            "📚 Read something interesting",
        ]


def get_productivity_suggestions(user_context: Optional[str] = None) -> list[str]:
    """Suggest productivity tips based on data."""
    suggestions = [
        "✅ Pomodoro: 25 min work + 5 min break",
        "📝 Break down big tasks into smaller ones",
        "🎯 Focus on 3 main goals today",
        "⏱ Track time spent on each task",
        "📱 Disable notifications for 1 hour",
        "🌿 Take a 5-min walk every hour",
        "💧 Drink water - stay focused",
        "🎵 Background music can boost focus",
    ]
    return suggestions


def suggest_meeting_prep(meeting_title: str, minutes_until: int) -> str:
    """Generate meeting preparation suggestions."""
    suggestions = []
    
    if minutes_until > 30:
        suggestions.append("📋 Prepare your agenda/notes")
        suggestions.append("🔗 Check meeting link and test audio/video")
        suggestions.append("📊 Gather relevant documents")
    elif minutes_until > 10:
        suggestions.append("👕 Make yourself presentable")
        suggestions.append("🔊 Test microphone and speakers")
        suggestions.append("📍 Find a quiet place for the meeting")
    elif minutes_until > 0:
        suggestions.append("🎤 Join the meeting call")
        suggestions.append("🔇 Mute until you speak (if needed)")
        suggestions.append("👋 Greet everyone when you join")
    else:
        suggestions.append("📞 You're late! Try to join ASAP")
    
    return "\n".join(suggestions)


def suggest_research_topics(query: str) -> list[str]:
    """Suggest related topics to research."""
    topics = []
    query_lower = query.lower()
    
    # Map queries to suggested research angles
    if "python" in query_lower:
        topics = ["Python performance", "Python frameworks", "Python async/await", "Python design patterns"]
    elif "machine learning" in query_lower or "ai" in query_lower or "llm" in query_lower:
        topics = ["Large Language Models", "Fine-tuning LLMs", "AI safety", "Prompt engineering"]
    elif "web" in query_lower:
        topics = ["REST APIs", "GraphQL", "WebSockets", "Microservices"]
    elif "database" in query_lower or "sql" in query_lower:
        topics = ["Query optimization", "Indexing", "Caching strategies", "Data normalization"]
    elif "javascript" in query_lower or "js" in query_lower:
        topics = ["React internals", "Node.js performance", "TypeScript", "Async patterns"]
    else:
        topics = [
            f"Best practices for {query}",
            f"Common pitfalls in {query}",
            f"Tools and libraries for {query}",
            f"Security in {query}",
        ]
    
    return topics


def suggest_file_organization() -> list[str]:
    """Suggest how to organize files for better productivity."""
    return [
        "📁 Create project folders: Projects, Work, Archive, Temp",
        "🏷 Tag files with project names or dates",
        "🔍 Use consistent naming: YYYY-MM-DD_ProjectName_Description",
        "🗑 Regular cleanup: move old files to Archive",
        "📌 Keep 'Current Work' folder for active projects",
        "🔐 Backup important files weekly",
        "📚 Create README in each project folder",
    ]


def get_time_based_suggestion() -> str:
    """Get a time-based suggestion for better habits."""
    hour = datetime.now().hour
    
    if hour == 9:
        return "🌅 Morning standup time? Check your goals for today"
    elif hour == 12:
        return "🍽 Time for lunch! Don't skip meals"
    elif hour == 15:
        return "😴 Afternoon slump? Take a 15-min power nap or walk"
    elif hour == 17:
        return "🏁 End of workday! Review what you accomplished"
    elif hour == 20:
        return "🌙 Evening wind-down time. Prepare for tomorrow"
    elif hour == 22:
        return "😴 Getting late. Consider sleeping soon for better next day"
    else:
        return "💡 Keep focused on your current task"
