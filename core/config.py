# 상수 및 설정 
import os
from typing import Final


NAI_API_KEY: Final[str] = os.environ["NOVELAI_API_KEY"]
MODEL: Final[str] = "nai-diffusion-4-5-full"
WIDTH: Final[int] = 1216
HEIGHT: Final[int] = 832
STEPS: Final[int] = 28
BASE_PROMPT: Final[str] = """1girl, -1::multiple views::, 3d, 

0.9::artist:teshima nari::, 
1.9::artist:ie (raarami)::, 
1.5::artist:umigraphics, artist:hoo bamon::, 
0.9::artist:gogalking::, 
1.7::artist:ratatatat74 ::, 
1.7::artist:yomu (sgt epper)::, 
2.5::artist:sofra::, 
1.5::artist:ms. tsu::, 
1.1::artist:2n5 ::, 
0.5::artist:teshima nari::, 

-5::artist collaboration::, year 2025, year 2024, newest, 

flat color, -1::nose, lips::, dot nose, pale color, 

-2::big hair::, 0.5::expressionless::, mature female, -2::child::, -1::loli::, -3::muscular::, -1::skinny::, 3::small breasts::, flat chest, 

-2::simple illustration, simple background::, detailed background, 2::official art, commission, best illustration, clear image, blender (medium), photoshop (medium)::, masterpiece, best quality, very aesthetic, incredibly absurdres, highly detailed,
full body, ::cowboy shot::, -2::portrait, straight-on::, 4::dutch angle:: 
"""
NEGATIVE_PROMPT:Final[str] = """text, logo, watermark, too many watermarks, blank page, text-only page, reference, username, signature, 

artist collaboration, 

variant set, large variant set, 4koma, 2koma, toon (style), chibi, turnaround, 

film grain, monochrome, dithering, halftone, screentones, dated, old, 1990s (style), 

mutation, deformed, distorted, disfigured, artistic error, distorted anatomy, anatomical structure error, asymmetrical face, unnatural hair, bad eyes, cloudy eyes, blank eyes, bad proportions, bad limb, extra digits, fewer digits, bad legs, extra legs, amputee, distorted composition, bad perspective, 

multiple views, negative space, animation error, chromatic aberration, disorganized colors, scan artifacts, jpeg artifacts, vertical lines, vertical banding, 

worst quality, bad quality, lowres, blurry, upscaled, fewer details, unfinished, incomplete, amateur, cheesy, unsatisfactory, inadequate, deficient, subpar, poor, displeasing, very displeasing, bad illustration, bad portrait, sketch, 

artist:xinzoruo, artist:milkpanda, makeup, """
CACHE_LIMIT_BYTES: Final[int] = 100 * 1024 * 1024