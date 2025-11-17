"""
Sample fixtures for Django messaging platform database models.

Provides realistic test data for development, testing, and demonstration purposes.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Conversation, Message, UserRole
import uuid


User = get_user_model()


def create_sample_users():
    """Create sample users with different roles."""
    users = {}
    
    # Admin user
    users['admin'] = User.objects.create_user(
        email='admin@messaging.com',
        password='admin123',
        first_name='System',
        last_name='Administrator',
        role=UserRole.ADMIN
    )
    
    # Host users
    users['host1'] = User.objects.create_user(
        email='john.doe@example.com',
        password='password123',
        first_name='John',
        last_name='Doe',
        role=UserRole.HOST
    )
    
    users['host2'] = User.objects.create_user(
        email='jane.smith@example.com',
        password='password123',
        first_name='Jane',
        last_name='Smith',
        role=UserRole.HOST
    )
    
    users['host3'] = User.objects.create_user(
        email='mike.wilson@example.com',
        password='password123',
        first_name='Mike',
        last_name='Wilson',
        role=UserRole.HOST
    )
    
    # Guest users
    users['guest1'] = User.objects.create_user(
        email='sarah.brown@example.com',
        password='password123',
        first_name='Sarah',
        last_name='Brown',
        role=UserRole.GUEST
    )
    
    users['guest2'] = User.objects.create_user(
        email='david.jones@example.com',
        password='password123',
        first_name='David',
        last_name='Jones',
        role=UserRole.GUEST
    )
    
    return users


def create_sample_conversations(users):
    """Create sample conversations between users."""
    conversations = {}
    
    # Direct message between host1 and host2
    conversation1 = Conversation.objects.create(title='John & Jane Chat')
    conversation1.add_participant(users['host1'])
    conversation1.add_participant(users['host2'])
    conversations['direct_chat'] = conversation1
    
    # Group conversation with multiple users
    group_conversation = Conversation.objects.create(
        title='Project Discussion',
        description='Discussion about the new messaging platform project'
    )
    group_conversation.add_participant(users['admin'], is_admin=True)
    group_conversation.add_participant(users['host1'])
    group_conversation.add_participant(users['host2'])
    group_conversation.add_participant(users['host3'])
    conversations['group_chat'] = group_conversation
    
    # Another direct message
    conversation2 = Conversation.objects.create(title='Mike & Sarah Chat')
    conversation2.add_participant(users['host3'])
    conversation2.add_participant(users['guest1'])
    conversations['another_direct_chat'] = conversation2
    
    return conversations


def create_sample_messages(users, conversations):
    """Create sample messages for conversations."""
    messages = []
    
    # Messages for direct chat
    direct_messages = [
        {
            'sender': users['host1'],
            'conversation': conversations['direct_chat'],
            'message_body': 'Hi Jane! How are you doing with the messaging platform project?',
            'sent_at': timezone.now() - timedelta(hours=2)
        },
        {
            'sender': users['host2'],
            'conversation': conversations['direct_chat'],
            'message_body': 'Hi John! Things are going well. I just finished the user model implementation.',
            'sent_at': timezone.now() - timedelta(hours=1, minutes=45)
        },
        {
            'sender': users['host1'],
            'conversation': conversations['direct_chat'],
            'message_body': 'Great! That was one of the more complex parts. Have you started on the conversation model?',
            'sent_at': timezone.now() - timedelta(hours=1, minutes=30)
        },
        {
            'sender': users['host2'],
            'conversation': conversations['direct_chat'],
            'message_body': 'Yes, I just started. The many-to-many relationship with participants is quite interesting.',
            'sent_at': timezone.now() - timedelta(hours=1, minutes=15)
        }
    ]
    
    # Messages for group conversation
    group_messages = [
        {
            'sender': users['admin'],
            'conversation': conversations['group_chat'],
            'message_body': 'Welcome everyone to our project discussion! Please share your progress updates.',
            'sent_at': timezone.now() - timedelta(days=1)
        },
        {
            'sender': users['host1'],
            'conversation': conversations['group_chat'],
            'message_body': 'I have completed the User model with all the required validations and constraints.',
            'sent_at': timezone.now() - timedelta(days=1, hours=22)
        },
        {
            'sender': users['host2'],
            'conversation': conversations['group_chat'],
            'message_body': 'I finished the Conversation model including the participant management system.',
            'sent_at': timezone.now() - timedelta(days=1, hours=21)
        },
        {
            'sender': users['host3'],
            'conversation': conversations['group_chat'],
            'message_body': 'I am working on the Message model with reply threading functionality.',
            'sent_at': timezone.now() - timedelta(days=1, hours=20)
        },
        {
            'sender': users['admin'],
            'conversation': conversations['group_chat'],
            'message_body': 'Excellent progress! Let\'s schedule a code review session for tomorrow.',
            'sent_at': timezone.now() - timedelta(days=1, hours=19)
        },
        {
            'sender': users['host1'],
            'conversation': conversations['group_chat'],
            'message_body': 'Sounds good! I can also present the database indexing strategy we implemented.',
            'sent_at': timezone.now() - timedelta(days=1, hours=18)
        }
    ]
    
    # Messages for another direct chat
    direct_messages_2 = [
        {
            'sender': users['host3'],
            'conversation': conversations['another_direct_chat'],
            'message_body': 'Hey Sarah! How do you like the new messaging system?',
            'sent_at': timezone.now() - timedelta(hours=3)
        },
        {
            'sender': users['guest1'],
            'conversation': conversations['another_direct_chat'],
            'message_body': 'Hi Mike! It\'s quite impressive. I especially like the user role system.',
            'sent_at': timezone.now() - timedelta(hours=2, minutes=45)
        },
        {
            'sender': users['host3'],
            'conversation': conversations['another_direct_chat'],
            'message_body': 'Thanks! The role-based permissions were a key requirement for the platform.',
            'sent_at': timezone.now() - timedelta(hours=2, minutes=30)
        }
    ]
    
    # Create all messages
    all_messages = direct_messages + group_messages + direct_messages_2
    
    for msg_data in all_messages:
        message = Message.objects.create(
            sender=msg_data['sender'],
            conversation=msg_data['conversation'],
            message_body=msg_data['message_body']
        )
        messages.append(message)
    
    return messages


def run_fixture_creation():
    """Create all sample data fixtures."""
    print("Creating sample users...")
    users = create_sample_users()
    print(f"Created {len(users)} users")
    
    print("Creating sample conversations...")
    conversations = create_sample_conversations(users)
    print(f"Created {len(conversations)} conversations")
    
    print("Creating sample messages...")
    messages = create_sample_messages(users, conversations)
    print(f"Created {len(messages)} messages")
    
    # Print summary
    print("\n" + "="*50)
    print("SAMPLE DATA SUMMARY")
    print("="*50)
    print(f"Users: {User.objects.count()}")
    print(f"Conversations: {Conversation.objects.count()}")
    print(f"Messages: {Message.objects.count()}")
    print("\nSample users created:")
    for role, user in users.items():
        print(f"  - {user.display_name} ({user.email}) - {user.role}")
    
    print("\nConversations created:")
    for name, conv in conversations.items():
        print(f"  - {conv.title} ({conv.get_participant_count()} participants)")
    
    return users, conversations, messages


if __name__ == '__main__':
    # Run fixture creation when script is executed directly
    import os
    import django
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'messaging_app.settings')
    django.setup()
    
    run_fixture_creation()