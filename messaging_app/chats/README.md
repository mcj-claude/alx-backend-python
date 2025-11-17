# Django Messaging Platform Database Schema

A comprehensive Django database schema implementation for a scalable messaging platform with three core models: User, Conversation, and Message. This implementation follows Django ORM best practices with robust validation, referential integrity, and optimized indexing for large-scale message handling.

## 📋 Database Schema Overview

### Models Implemented

#### 1. **User Model** (Extended AbstractBaseUser)
- **Primary Key**: UUIDField with automatic generation for scalability
- **Authentication**: Case-insensitive unique email with Django auth integration
- **Profile Fields**: first_name, last_name (NOT NULL), optional phone_number
- **Role Management**: Guest, Host, Admin roles with hierarchical permissions
- **Audit Trail**: created_at timestamp with timezone awareness
- **Django Integration**: USERNAME_FIELD='email', REQUIRED_FIELDS configured

#### 2. **Conversation Model**
- **Primary Key**: UUIDField for scalable conversation management
- **Participants**: Many-to-many relationship through ConversationParticipants through table
- **Validation**: Minimum 2 participants, participant management with admin privileges
- **Soft Deletion**: is_active flag with proper validation
- **Metadata**: participant_count tracking for performance optimization

#### 3. **Message Model**
- **Primary Key**: UUIDField for message uniqueness and scalability
- **Relationships**: Sender (CASCADE), Conversation (CASCADE), optional reply_to
- **Content**: message_body TextField with 5000 character limit validation
- **Threading Support**: Reply-to functionality for message conversations
- **Timestamps**: sent_at with automatic population
- **Soft Deletion**: is_deleted flag with deletion tracking

#### 4. **ConversationParticipants (Through Table)**
- **Relationship Management**: Bidirectional User-Conversation relationship
- **Admin Tracking**: is_admin flag for conversation-level permissions
- **Participation History**: joined_at timestamp, last_read_at for read receipts
- **Validation**: Prevents duplicate participants, ensures proper membership

## 🗄️ Database Specifications

### User Table Schema
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    first_name VARCHAR(150) NOT NULL,
    last_name VARCHAR(150) NOT NULL,
    phone_number VARCHAR(20),
    role VARCHAR(10) NOT NULL CHECK (role IN ('guest', 'host', 'admin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_staff BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    
    CONSTRAINT valid_user_role CHECK (role IN ('guest', 'host', 'admin')),
    CONSTRAINT non_empty_first_name CHECK (first_name IS NOT NULL AND length(first_name) > 0),
    CONSTRAINT non_empty_last_name CHECK (last_name IS NOT NULL AND length(last_name) > 0),
    CONSTRAINT unique_user_email UNIQUE (email)
);
```

### Conversation Table Schema
```sql
CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    CONSTRAINT minimum_participants CHECK (participant_count >= 2),
    CONSTRAINT non_negative_message_count CHECK (message_count >= 0)
);
```

### Message Table Schema
```sql
CREATE TABLE messages (
    message_id UUID PRIMARY KEY,
    sender_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    message_body TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    reply_to UUID REFERENCES messages(message_id) ON DELETE SET NULL,
    
    CONSTRAINT non_empty_message_body CHECK (message_body IS NOT NULL AND length(message_body) > 0),
    CONSTRAINT message_body_length_limit CHECK (length(message_body) <= 5000),
    CONSTRAINT read_at_requires_is_read CHECK (read_at IS NULL OR is_read = TRUE),
    CONSTRAINT deleted_at_requires_is_deleted CHECK (deleted_at IS NULL OR is_deleted = TRUE)
);
```

### ConversationParticipants Table Schema
```sql
CREATE TABLE conversation_participants (
    id SERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_admin BOOLEAN DEFAULT FALSE,
    last_read_at TIMESTAMP,
    
    UNIQUE (conversation_id, user_id)
);
```

## 🔍 Indexing Strategy

### User Model Indexes
- **Primary Key**: Auto-indexed (user_id)
- **email**: Unique index for authentication lookups
- **role**: Index for role-based filtering
- **created_at**: Index for chronological queries
- **is_active**: Index for active user filtering

### Conversation Model Indexes
- **Primary Key**: Auto-indexed (conversation_id)
- **created_at**: Index for conversation listing
- **is_active**: Index for active conversation filtering
- **participant_count**: Index for participant-based queries

### Message Model Indexes
- **Primary Key**: Auto-indexed (message_id)
- **conversation**: Index for message retrieval in conversations
- **sender**: Index for sender-based message queries
- **sent_at**: Index for chronological message ordering
- **Composite Indexes**:
  - `(conversation, sent_at)`: For conversation message history
  - `(conversation, is_deleted, sent_at)`: For efficient message filtering
  - `(sender, sent_at)`: For sender message queries

### ConversationParticipants Indexes
- **conversation**: Index for participant queries
- **user**: Index for user participation queries
- **is_admin**: Index for admin participant filtering
- **joined_at**: Index for participation timeline
- **Composite Index**: `(conversation, is_admin)` for admin participant lookups

## 🔒 Data Integrity & Constraints

### Validation Rules
1. **User Validation**:
   - Email must be unique (case-insensitive)
   - First and last names are required
   - Role must be one of: guest, host, admin
   - Email validation using Django's built-in validators

2. **Conversation Validation**:
   - Minimum 2 participants required
   - Cannot remove participants if it would leave fewer than 2
   - Validates participant relationships on creation

3. **Message Validation**:
   - Sender must be a participant in the conversation
   - Message content cannot be empty
   - Maximum message length: 5000 characters
   - Reply-to message must be from same conversation

### Referential Integrity
- **CASCADE Deletion**: Messages and conversation participants are deleted when parent records are deleted
- **SET NULL**: Deleted_by field in messages is set to NULL when user is deleted
- **Foreign Key Constraints**: All relationships enforce referential integrity

## 🧪 Testing & Validation

### Test Suite Coverage
The implementation includes comprehensive tests covering:

1. **User Model Tests**:
   - User creation with all required fields
   - Email uniqueness constraint validation
   - Role-based permission testing
   - Authentication functionality

2. **Conversation Model Tests**:
   - Conversation creation and participant management
   - Minimum participant validation
   - Participant addition/removal logic
   - String representation testing

3. **Message Model Tests**:
   - Message creation with validation
   - Content validation (non-empty, length limits)
   - Sender validation (must be participant)
   - Soft delete functionality
   - Reply thread functionality

4. **Integration Tests**:
   - Complete conversation workflow
   - Data integrity constraints
   - Index verification
   - Permission system validation

### Running Tests
```bash
# Run all tests
python manage.py test chats

# Run specific test class
python manage.py test chats.tests.UserModelTest

# Run with coverage
coverage run --source='.' manage.py test chats
coverage report
```

### Validation Script
The included validation script (`validate.py`) tests:
- Model creation
- Relationship integrity
- Database constraints
- Index verification
- Permission system functionality

```bash
# Run validation
python messaging_app/chats/validate.py
```

## 📊 Performance Optimizations

### Query Optimization
1. **Select Related**: Optimized foreign key relationships
2. **Database Indexes**: Strategic placement for common query patterns
3. **Cached Counts**: participant_count and message_count fields
4. **Composite Indexes**: Multi-column indexes for complex queries

### Efficient Retrieval Patterns
- **Conversation Queries**: Optimized for user conversation lists
- **Message Retrieval**: Chronological ordering with proper indexes
- **Participant Management**: Efficient through table queries
- **Read Receipts**: Optimized read status tracking

### Scalability Considerations
- UUID primary keys for horizontal scaling
- Proper indexing for large dataset performance
- Efficient relationship queries using Django ORM
- Soft deletion for data retention without performance impact

## 🔧 Django Integration

### Authentication System
- **AbstractBaseUser Extension**: Full Django auth compatibility
- **Custom Permissions**: Role-based permission system
- **Admin Integration**: Django admin interface ready
- **Session Management**: Compatible with Django sessions

### Admin Interface
- **UserAdmin**: Comprehensive user management with role-based filtering
- **ConversationAdmin**: Conversation management with participant oversight
- **MessageAdmin**: Message management with conversation and sender filtering
- **ConversationParticipantAdmin**: Participant relationship management

### Configuration Requirements
Add to `settings.py`:
```python
AUTH_USER_MODEL = 'chats.User'

INSTALLED_APPS = [
    # ... other apps
    'chats',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'messaging_db',
        'USER': 'username',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## 📝 Usage Examples

### Creating Users
```python
from chats.models import User, UserRole

# Create a host user
host = User.objects.create_user(
    email='john@example.com',
    password='password123',
    first_name='John',
    last_name='Doe',
    role=UserRole.HOST
)

# Create an admin user
admin = User.objects.create_superuser(
    email='admin@example.com',
    password='admin123',
    first_name='Admin',
    last_name='User',
    role=UserRole.ADMIN
)
```

### Creating Conversations
```python
# Create a conversation
conversation = Conversation.objects.create(title='Team Chat')

# Add participants
conversation.add_participant(host, is_admin=True)
conversation.add_participant(admin)

# Check if user is participant
if conversation.is_participant(host):
    print("Host is participating in this conversation")
```

### Sending Messages
```python
# Send a message
message = Message.objects.create(
    sender=host,
    conversation=conversation,
    message_body='Hello everyone! Welcome to our team chat.'
)

# Send a reply
reply = Message.objects.create(
    sender=admin,
    conversation=conversation,
    message_body='Thanks for the warm welcome!',
    reply_to=message
)
```

### Querying Data
```python
# Get user's conversations
user_conversations = conversation.conversations.filter(is_active=True)

# Get messages in a conversation
messages = conversation.messages.filter(is_deleted=False).order_by('sent_at')

# Get conversation participants
participants = conversation.participants.all()

# Get user's sent messages
sent_messages = host.sent_messages.filter(is_deleted=False)
```

## 🚀 Migrations & Setup

### Database Migration
```bash
# Create migrations
python manage.py makemigrations chats

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### Sample Data
Load sample data for testing and development:
```bash
# Using Django shell
python manage.py shell

# Load fixtures
from chats.fixtures import run_fixture_creation
users, conversations, messages = run_fixture_creation()
```

## 🔍 API Development Notes

### Serialization Considerations
- User model requires custom serializer due to extended AbstractBaseUser
- Conversation and Message models use standard Django REST Framework serialization
- Consider nested serialization for complex data structures

### ViewSet Patterns
- **UserViewSet**: Extended authentication and profile management
- **ConversationViewSet**: CRUD operations with participant management
- **MessageViewSet**: Message operations with conversation context

### Permissions
- User permissions based on role (guest, host, admin)
- Conversation participants can view and send messages
- Admin users have global moderation capabilities

## 📈 Monitoring & Maintenance

### Database Monitoring
- Monitor query performance using Django Debug Toolbar
- Track database growth and index usage
- Monitor connection pool usage

### Maintenance Tasks
- Regular database backup and restore testing
- Index optimization and maintenance
- Soft delete cleanup for old messages

### Performance Tuning
- Consider database partitioning for very large message tables
- Implement caching for frequently accessed conversations
- Monitor and optimize slow queries

## 🔒 Security Considerations

### Data Protection
- Passwords hashed using Django's built-in password hashers
- User sessions managed by Django
- CSRF protection on all forms

### Access Control
- Role-based permissions system
- Conversation-level access control
- Message read/write permissions

### Audit Trail
- Created_at timestamps on all models
- Deleted_at timestamps for soft deletion
- User tracking for deletions

## 🛠️ Development Workflow

### Code Organization
```
chats/
├── models.py          # Core model definitions
├── admin.py          # Django admin interface
├── tests.py          # Comprehensive test suite
├── fixtures.py       # Sample data fixtures
├── validate.py       # Schema validation script
└── README.md         # This documentation
```

### Best Practices
- Follow Django coding standards
- Use model forms for validation
- Implement proper error handling
- Document complex business logic
- Write comprehensive tests

## 📚 Additional Resources

### Django Documentation
- [Django Models](https://docs.djangoproject.com/en/4.2/topics/db/models/)
- [Custom User Models](https://docs.djangoproject.com/en/4.2/topics/auth/customizing/)
- [Database Indexing](https://docs.djangoproject.com/en/4.2/ref/models/fields/#database-indexes)

### Database Design
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Database Normalization](https://en.wikipedia.org/wiki/Database_normalization)
- [Performance Optimization](https://wiki.postgresql.org/wiki/Performance_Optimization)

---

## ✅ Implementation Checklist

- ✅ **User Model**: Extended AbstractBaseUser with UUID primary key
- ✅ **Conversation Model**: Many-to-many relationships with validation
- ✅ **Message Model**: Sender/conversation FKs with content validation
- ✅ **Constraints**: Unique, check, and foreign key constraints
- ✅ **Indexing**: Comprehensive index strategy for performance
- ✅ **Admin Interface**: Django admin configuration for all models
- ✅ **Testing**: Comprehensive test suite with coverage
- ✅ **Validation**: Schema validation and constraint testing
- ✅ **Fixtures**: Sample data for development and testing
- ✅ **Documentation**: Complete implementation documentation

This implementation provides a production-ready, scalable database schema that follows Django ORM best practices while meeting all specified requirements for the messaging platform.