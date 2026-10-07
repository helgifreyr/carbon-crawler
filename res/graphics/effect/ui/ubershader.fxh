float4x4 g_uiTransforms[32];

float4 UIViewportSize;

texture2D PrimaryTexture0;
sampler PrimarySampler0 = sampler_state
{
    Texture = <PrimaryTexture0>;
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = None;
    AddressU = Clamp;
    AddressV = Clamp;
};

static const uint EFFECT_FILL_AA = 1;
static const uint EFFECT_FIRST_TEXTURED = 32;
static const uint EFFECT_FIRST_TWO_TEXTURE = 64;

static const uint BLEND_NONE = 0;
static const uint BLEND_BLEND = 1;
static const uint BLEND_ADD = 2;
static const uint BLEND_ADDX2 = 3;

struct SpriteVertex
{
    float3 pos : POSITION;
    float4 color : COLOR0;
    float2 uv0 : TEXCOORD0;
    float2 uv1 : TEXCOORD1;
    float4 clipRect : TEXCOORD2;
    float glow : TEXCOORD3;
    uint4 data : BLENDINDICES;
    float4 outlineColor : COLOR1;
    float outlineThreshold : TEXCOORD4;
};

struct SpritePixel
{
    float4 pos : SV_Position;
    float4 color : COLOR0;
    float2 uv0 : TEXCOORD0;
    float4 clipRect : TEXCOORD1;
    float3 settings : TEXCOORD2;
};

SpritePixel SpriteVS(SpriteVertex v)
{
    float4 p = mul(float4(v.pos.xy, 0.0, 1.0), g_uiTransforms[v.data.x]);
    float2 size = max(UIViewportSize.xy, float2(1.0, 1.0));

    uint blend = v.data.y & 3;
    float opacity = blend == BLEND_NONE ? 1.0 : blend == BLEND_BLEND ? v.color.a : 0.0;
    float4 color = v.color;
    if (blend == BLEND_ADDX2)
        color.rgb *= 2.0;

    SpritePixel o;
    o.pos = float4(2.0 * p.x / size.x - 1.0, 1.0 - 2.0 * p.y / size.y, 0.0, 1.0);
    o.color = color;
    o.uv0 = v.uv0;
    o.clipRect = v.clipRect;
    float targetsColor = (v.data.y & 8) ? 1.0 : 0.0;
    o.settings = float3(opacity, (float)v.data.z, targetsColor);
    return o;
}

float4 SpritePS(SpritePixel i) : SV_Target
{
    if (i.clipRect.z > i.clipRect.x && i.clipRect.w > i.clipRect.y)
    {
        clip(i.pos.x - i.clipRect.x);
        clip(i.clipRect.z - i.pos.x);
        clip(i.pos.y - i.clipRect.y);
        clip(i.clipRect.w - i.pos.y);
    }

    float opacity = i.settings.x;
    uint effect = (uint)i.settings.y;
    float4 c = i.color;
    float alpha = opacity;
    if (effect >= EFFECT_FIRST_TEXTURED && effect < EFFECT_FIRST_TWO_TEXTURE)
    {
        float4 tex = tex2D(PrimarySampler0, i.uv0);
        c *= tex;
        alpha = tex.a * opacity;
    }
    c.rgb *= c.a;
    return float4(c.rgb, alpha) * i.settings.z;
}

technique Main
{
    pass P0
    {
        AlphaBlendEnable = true;
        SrcBlend = One;
        DestBlend = InvSrcAlpha;
        ZEnable = false;
        ZWriteEnable = false;
        CullMode = None;
        VertexShader = compile vs_3_0 SpriteVS();
        PixelShader = compile ps_3_0 SpritePS();
    }
}
