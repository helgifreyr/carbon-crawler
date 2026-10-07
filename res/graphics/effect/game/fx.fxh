// Procedural particles: each quad's four corners share random seeds (NORMAL, TEXCOORD1), and the vertex shader
// places the particle from the effect's age alone, so a whole burst is one draw and one parameter per frame.
float4 FxTime < bool SasUiVisible = true; > = float4(0.0, 1.0, 0.0, 0.0);
float4 FxColor < bool SasUiVisible = true; > = float4(1.0, 0.7, 0.3, 1.0);
float4 FxColorEnd < bool SasUiVisible = true; > = float4(0.6, 0.1, 0.0, 1.0);
float4 FxSize < bool SasUiVisible = true; > = float4(0.12, 0.02, 0.0, 0.0);

texture2D DiffuseMap;
sampler DiffuseSampler = sampler_state
{
    Texture = <DiffuseMap>;
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = None;
    AddressU = Clamp;
    AddressV = Clamp;
};

struct FxVSIn
{
    float3 pos : POSITION;
    float3 seed : NORMAL;
    float2 corner : TEXCOORD0;
    float2 seed2 : TEXCOORD1;
};

struct FxVSOut
{
    float4 pos : SV_Position;
    float2 uv : TEXCOORD0;
    float4 color : TEXCOORD1;
};

FxVSOut FxBillboard(float3 local, float2 corner, float size, float u)
{
    FxVSOut o;
    float4 world = mul(float4(local, 1.0), WorldMat);
    world.y = max(world.y, -0.48);
    float4 view = mul(world, ViewMat);
    view.xy += (corner * 2.0 - 1.0) * float2(1.0, -1.0) * size;
    o.pos = mul(view, ProjectionMat);
    o.uv = corner;
    float fade = 1.0 - u;
    o.color = float4(lerp(FxColor.rgb, FxColorEnd.rgb, u) * FxColor.a, fade * fade);
    return o;
}

float4 FxPS(FxVSOut i) : SV_Target
{
    float a = tex2D(DiffuseSampler, i.uv).a * i.color.a;
    return float4(i.color.rgb * a, 1.0);
}
