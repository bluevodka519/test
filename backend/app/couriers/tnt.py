"""TNT: optional bonus in the brief, not implemented.

TNT uses XML (Rated Transit Times, consignment tracking via Secured
Weblinking). Kept behind the same interface as Australia Post so a real
client can replace this stub without touching the order service.
"""
from app.models import TrackingResult, TrackingStatus


class TntClient:
    async def track_many(self, tracking_nos: list[str]) -> dict[str, TrackingResult]:
        return {
            no: TrackingResult(
                status=TrackingStatus.NOT_IMPLEMENTED,
                carrier="TNT",
                tracking_no=no,
                message="TNT tracking is not implemented (optional bonus). No live result is shown.",
            )
            for no in tracking_nos
        }
