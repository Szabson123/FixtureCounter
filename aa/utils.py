import threading
from django.core.mail import get_connection, EmailMultiAlternatives
from .models import UserToMail

def _send_emails_process(group_name, subject, body):
    emails = UserToMail.objects.filter(
        mail_group__name=group_name
    ).values_list('email', flat=True)

    connection = get_connection()
    connection.open()
    
    messages = []
    
    for email in emails:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email='spea_card@biton.pl',
            to=[email],
            connection=connection
        )
        messages.append(msg)
        
        if len(messages) >= 20:
            connection.send_messages(messages)
            messages = []
            
    if messages:
        connection.send_messages(messages)
        
    connection.close()

def send_mass_email_threaded(group_name, subject, body):
    email_thread = threading.Thread(
        target=_send_emails_process,
        args=(group_name, subject, body)
    )
    email_thread.start()