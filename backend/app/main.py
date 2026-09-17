from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

# Serve uploaded photos. The reviewer dashboard reads verdicts months after
# the fact, and the vendor sees the image they submitted next to the result,
# so these need to be fetchable by URL.
#
# NOTE: these are unauthenticated static mounts. Images are visible to anyone
# who knows the filename, which is why uploads are stored under a random
# UUID rather than a guessable id. Moving to authenticated, per-stall image
# delivery is a Phase 4 concern (it lands naturally with the public consumer
# profile, which needs a *deliberately* public subset).
_scan_dir = settings.scan_upload_path
_scan_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads/scans", StaticFiles(directory=_scan_dir), name="scan-uploads")

_hygiene_dir = settings.hygiene_upload_path
_hygiene_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/uploads/hygiene",
    StaticFiles(directory=_hygiene_dir),
    name="hygiene-uploads",
)


@app.get("/")
def root():
    return {"message": "Welcome to Smart Street Food Safety AI API"}
