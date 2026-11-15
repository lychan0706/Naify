from queue import Queue
from typing import Final


generation_queue = Queue()
# BASE_PROMPT: Final[str] = """1girl, -1::multiple views::, -5::artist collaboration::, year 2025, year 2024, newest, 1.7::artist:umigraphics, artist:hoo bamon::, 2.5::artist:sofra::, 3.0::artist:maratang::, 1.5::artist:ratatatat74 ::, 1.4::artist:norisukexxy::, 1.1::artist:ms. tsu::, 0.9::artist:yomu (sgt epper)::, 0.7::artist:wanke::, 0.5::artist:kurono mitsuki ::,  -3::child::, flat chest, 4::3d, blender (medium), flat color, cel rendering, hatching (texture)::, -3::unfinished, sketch, outline::, pale color, 2::official art, best illustration::, masterpiece, best quality, very aesthetic, incredibly absurdres, highly detailed"""
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