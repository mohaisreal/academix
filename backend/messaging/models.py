from datetime import timedelta

from django.db import models
from django.conf import settings
from django.utils import timezone


# Rolling window for the message-notification-batching spec: at most one
# notification/email batch per (recipient, thread root) within this window.
NOTIFICATION_BATCH_WINDOW = timedelta(minutes=5)


class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages'
    )
    subject = models.CharField(max_length=300, blank=True, default='')
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_recipient = models.BooleanField(default=False)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender.username} → {self.recipient.username}: {self.subject}"


class MessageNotificationBatchManager(models.Manager):
    def register_message(self, recipient, root):
        """
        Record that a new message arrived for *recipient* in the thread
        rooted at *root*, and decide whether a notification/email should be
        sent now.

        Returns ``(batch, should_notify)``:
          - If an active batch (``last_message_at`` within
            ``NOTIFICATION_BATCH_WINDOW``) already exists for this
            recipient/thread, it is touched (``last_message_at`` bumped to
            now) and ``should_notify`` is ``False`` — the earlier
            notification/email already covers this window.
          - Otherwise a new batch is created and ``should_notify`` is
            ``True`` — this message starts a new window and should trigger
            a notification/email.
        """
        cutoff = timezone.now() - NOTIFICATION_BATCH_WINDOW
        active_batch = (
            self.filter(recipient=recipient, root=root, last_message_at__gte=cutoff)
            .order_by('-last_message_at')
            .first()
        )
        if active_batch is not None:
            active_batch.last_message_at = timezone.now()
            active_batch.save(update_fields=['last_message_at'])
            return active_batch, False

        batch = self.create(recipient=recipient, root=root, notification_sent=True)
        return batch, True


class MessageNotificationBatch(models.Model):
    """
    Tracks the rolling five-minute notification/email window for a single
    (recipient, thread root) pair. While ``last_message_at`` is within the
    batching window, new messages in the same thread reuse this batch
    instead of triggering another notification/email.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_notification_batches',
    )
    root = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='notification_batches',
    )
    last_message_at = models.DateTimeField(auto_now_add=True)
    notification_sent = models.BooleanField(default=False)

    objects = MessageNotificationBatchManager()

    class Meta:
        ordering = ['-last_message_at']

    def __str__(self):
        return f"Batch for {self.recipient.username} on thread {self.root_id}"
