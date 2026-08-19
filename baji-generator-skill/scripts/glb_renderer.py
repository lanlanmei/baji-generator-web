"""Optional GLB/WebGL capability probe; no browser runtime is bundled."""
from pathlib import Path
ROOT=Path(__file__).parents[1]
GLB=ROOT/'assets'/'models'/'badge_master.glb'
def available(): return False
def unavailable_reason(): return 'No bundled headless WebGL runtime or validated badge_master.glb is present.'

