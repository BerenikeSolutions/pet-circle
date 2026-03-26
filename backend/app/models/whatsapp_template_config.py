"""
WhatsappTemplateConfig model — master registry of all WhatsApp-approved templates.

Each row stores the template name, approved body text (with {{1}}, {{2}} placeholders),
parameter count, and metadata. Used by whatsapp_sender.get_template_body() to render
the complete message at send time before saving to reminders and nudge_delivery_log.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class WhatsappTemplateConfig(Base):
    """Registry of all WhatsApp Business API approved templates used by PetCircle."""

    __tablename__ = "whatsapp_template_configs"

    template_name = Column(String(100), primary_key=True)
    body_text = Column(Text, nullable=False, default="")
    # Number of {{n}} parameters the template accepts (0 for static templates).
    param_count = Column(Integer, nullable=False, default=0)
    language_code = Column(String(10), nullable=False, default="en")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
