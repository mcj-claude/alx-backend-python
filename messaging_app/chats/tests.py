"""
Test suite for Django messaging platform database models.

Tests validate model relationships, constraints, validation rules,
and business logic for User, Conversation, and Message models.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from .models import Conversation, Message, ConversationParticipant, UserRole
import uuid


User = get_user_model()


class UserModelTest(TestCase):
    """Test cases for User model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user_data = {
            'email': 'test@example.com',
            'password': 'testpassword123',
            'first_name': 'Test',
            'last_name': 'User',
            'role': UserRole.HOST
        }
    
    def test_create_user_success(self):
        """Test successful user creation."""
        user = User.objects.create_user(**self.user_data)
        
        # Verify user was created
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.role, UserRole.HOST)
        self.assertTrue(user.check_password('testpassword123'))
        self.assertEqual(str(user), 'Test User (test@example.com)')
    
    def test_create_user_missing_email(self):
        """Test user creation fails without email."""
        self.user_data['email'] = ''
        with self.assertRaises(ValueError):
            User.objects.create_user(**self.user_data)
    
    def test_user_email_unique(self):
        """Test that email addresses must be unique."""
        # Create first user
        User.objects.create_user(**self.user_data)
        
        # Try to create second user with same email
        self.user_data['first_name'] = 'Second'
        with self.assertRaises(IntegrityError):
            User.objects.create_user(**self.user_data)
    
    def test_user_can_create_conversations(self):
        """Test user conversation creation permissions."""
        host_user = User.objects.create_user(**self.user_data)
        guest_user = User.objects.create_user(
            email='guest@example.com',
            password='password123',
            first_name='Guest',
            last_name='User',
            role=UserRole.GUEST
        )
        
        # Host should be able to create conversations
        self.assertTrue(host_user.can_create_conversations())
        
        # Guest should not be able to create conversations
        self.assertFalse(guest_user.can_create_conversations())


class ConversationModelTest(TestCase):
    """Test cases for Conversation model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='password123',
            first_name='User',
            last_name='One',
            role=UserRole.HOST
        )
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='password123',
            first_name='User',
            last_name='Two',
            role=UserRole.HOST
        )
    
    def test_create_conversation_success(self):
        """Test successful conversation creation."""
        conversation = Conversation.objects.create()
        conversation.add_participant(self.user1)
        conversation.add_participant(self.user2)
        
        # Verify conversation was created
        self.assertTrue(Conversation.objects.filter(id=conversation.conversation_id).exists())
        self.assertEqual(conversation.get_participant_count(), 2)
        self.assertTrue(conversation.is_participant(self.user1))
        self.assertTrue(conversation.is_participant(self.user2))
    
    def test_conversation_participant_validation(self):
        """Test conversation participant validation rules."""
        conversation = Conversation.objects.create()
        conversation.add_participant(self.user1)
        conversation.add_participant(self.user2)
        
        # Try to remove last participant (should fail)
        with self.assertRaises(ValidationError):
            conversation.remove_participant(self.user1)


class MessageModelTest(TestCase):
    """Test cases for Message model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            email='sender@example.com',
            password='password123',
            first_name='Sender',
            last_name='User',
            role=UserRole.HOST
        )
        self.conversation = Conversation.objects.create()
        self.conversation.add_participant(self.user1)
    
    def test_create_message_success(self):
        """Test successful message creation."""
        message = Message.objects.create(
            sender=self.user1,
            conversation=self.conversation,
            message_body='Test message content'
        )
        
        # Verify message was created
        self.assertTrue(Message.objects.filter(id=message.message_id).exists())
        self.assertEqual(message.sender, self.user1)
        self.assertEqual(message.conversation, self.conversation)
        self.assertEqual(message.message_body, 'Test message content')
    
    def test_message_content_validation(self):
        """Test message content validation."""
        # Empty message should fail
        message = Message(
            sender=self.user1,
            conversation=self.conversation,
            message_body=''
        )
        with self.assertRaises(ValidationError):
            message.clean()
        
        # Very long message should fail
        long_message = 'x' * 5001
        message.message_body = long_message
        with self.assertRaises(ValidationError):
            message.clean()


class ConversationParticipantModelTest(TestCase):
    """Test cases for ConversationParticipant model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='password123',
            first_name='User',
            last_name='One',
            role=UserRole.HOST
        )
        self.conversation = Conversation.objects.create()
    
    def test_create_participant(self):
        """Test participant creation."""
        participant = ConversationParticipant.objects.create(
            conversation=self.conversation,
            user=self.user1,
            is_admin=True
        )
        
        # Verify participant was created
        self.assertTrue(
            ConversationParticipant.objects.filter(
                conversation=self.conversation,
                user=self.user1
            ).exists()
        )
        self.assertTrue(participant.is_admin)
    
    def test_unique_participant_constraint(self):
        """Test unique constraint on conversation-participant relationship."""
        # Create first participation
        ConversationParticipant.objects.create(
            conversation=self.conversation,
            user=self.user1
        )
        
        # Try to create duplicate participation (should fail)
        with self.assertRaises(IntegrityError):
            ConversationParticipant.objects.create(
                conversation=self.conversation,
                user=self.user1
            )