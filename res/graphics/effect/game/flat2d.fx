#include "common.fxh"

// Flat-coloured triangles in screen space, for the automap: positions are in map pixels, placed on screen by
// MapXform (scale, offset x, offset y) and cut to ClipRect (x0, y0, x1, y1), both in screen pixels.
float4 ScreenSize < bool SasUiVisible = true; > = float4(1280.0, 800.0, 0.0, 0.0);
float4 MapXform < bool SasUiVisible = true; > = float4(1.0, 0.0, 0.0, 0.0);
float4 ClipRect < bool SasUiVisible = true; > = float4(0.0, 0.0, 100000.0, 100000.0);

struct VSIn
{
    float3 pos : POSITION;
    float3 normal : NORMAL;
    float4 color : TEXCOORD0;
};

struct VSOut
{
    float4 pos : SV_Position;
    float4 color : TEXCOORD0;
    float2 screen : TEXCOORD1;
};

VSOut FlatVS(VSIn i)
{
    VSOut o;
    float2 s = i.pos.xy * MapXform.x + MapXform.yz;
    o.screen = s;
    o.pos = float4(s.x / ScreenSize.x * 2.0 - 1.0, 1.0 - s.y / ScreenSize.y * 2.0, 0.5, 1.0);
    o.color = i.color;
    return o;
}

float4 FlatPS(VSOut i) : SV_Target
{
    clip(float4(i.screen - ClipRect.xy, ClipRect.zw - i.screen));
    return i.color;
}

technique Main
{
    pass P0
    {
        ZEnable = false;
        ZWriteEnable = false;
        CullMode = None;
        AlphaBlendEnable = true;
        SrcBlend = SrcAlpha;
        DestBlend = InvSrcAlpha;
        VertexShader = compile vs_3_0 FlatVS();
        PixelShader = compile ps_3_0 FlatPS();
    }
}
