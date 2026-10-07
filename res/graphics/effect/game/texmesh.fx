#include "common.fxh"
#include "lit.fxh"

struct VSIn
{
    float3 pos : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
};

LitVSOut TexMeshVS(VSIn i)
{
    return LitVertex(i.pos, i.normal, i.uv);
}

float4 TexMeshPS(LitVSOut i) : SV_Target
{
    return float4(LitColor(i), 1.0);
}

technique Main
{
    pass P0
    {
        ZEnable = true;
        ZWriteEnable = true;
        CullMode = None;
        AlphaBlendEnable = false;
        VertexShader = compile vs_3_0 TexMeshVS();
        PixelShader = compile ps_3_0 TexMeshPS();
    }
}
