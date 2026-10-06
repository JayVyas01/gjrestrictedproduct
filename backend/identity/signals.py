"""Signals other apps may listen to, so identity never imports them.

`password_changed(sender=User, user=..., password=...)` is sent after a user changes their own
password and the change is saved, inside the request's transaction. `password` is the new plain
text password, held in memory only: a receiver must never store or log it as it is. (The demo app
keeps it encrypted in DemoCredential, in demo mode only.)
"""

from django.dispatch import Signal

password_changed = Signal()
