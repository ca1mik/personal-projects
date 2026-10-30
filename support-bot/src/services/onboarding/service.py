from __future__ import annotations

from enum import StrEnum

from src.models import Consent, User, UserPreference


class OnboardingStep(StrEnum):
    START = "start"
    ADULT_CONFIRMATION = "adult_confirmation"
    PRIVACY = "privacy"
    OFFER = "offer"
    DISCLAIMER = "disclaimer"
    CHECKIN = "checkin"
    READY = "ready"
    DENIED = "denied"


class OnboardingService:
    def get_next_step(
        self,
        *,
        user: User,
        consent: Consent | None,
        preference: UserPreference | None,
    ) -> OnboardingStep:
        if not user.is_adult_confirmed:
            return OnboardingStep.ADULT_CONFIRMATION

        if consent is None or not consent.privacy_accepted:
            return OnboardingStep.PRIVACY
        if not consent.offer_accepted:
            return OnboardingStep.OFFER
        if not consent.disclaimer_accepted:
            return OnboardingStep.DISCLAIMER
        if preference is None or not preference.checkin_consent_answered:
            return OnboardingStep.CHECKIN
        return OnboardingStep.READY

    def can_chat(self, *, user: User, consent: Consent | None) -> bool:
        return bool(
            user.is_adult_confirmed
            and consent
            and consent.privacy_accepted
            and consent.offer_accepted
            and consent.disclaimer_accepted
        )
