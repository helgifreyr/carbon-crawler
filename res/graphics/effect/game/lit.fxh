float4 LightDir < bool SasUiVisible = true; > = float4(-0.6, 0.7, 0.4, 0.0);
float4 SkyColor < bool SasUiVisible = true; > = float4(0.3, 0.33, 0.44, 1.0);
float4 GroundColor < bool SasUiVisible = true; > = float4(0.26, 0.2, 0.16, 1.0);
float4 KeyColor < bool SasUiVisible = true; > = float4(0.8, 0.76, 0.7, 1.0);
float4 RimColor < bool SasUiVisible = true; > = float4(0.35, 0.4, 0.55, 1.0);
float4 Emissive < bool SasUiVisible = true; > = float4(0.0, 0.0, 0.0, 0.0);
// x: strength, y: model-space floor height, z: fade height
float4 Occlusion < bool SasUiVisible = true; > = float4(0.0, 0.0, 1.0, 0.0);
// x: normal map strength, y: specular strength, z: specular power, w: rim strength
float4 Surface < bool SasUiVisible = true; > = float4(1.0, 0.5, 24.0, 0.6);

// Baked torch light, looked up by world XZ: LightMapRect is (x0, z0, 1/width, 1/depth), LightScale.x its strength.
float4 LightMapRect < bool SasUiVisible = true; > = float4(0.0, 0.0, 1.0, 1.0);
float4 LightScale < bool SasUiVisible = true; > = float4(0.0, 0.0, 0.0, 0.0);

texture2D LightMap;
sampler LightMapSampler = sampler_state
{
    Texture = <LightMap>;
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = None;
    AddressU = Clamp;
    AddressV = Clamp;
};

texture2D DiffuseMap;
sampler DiffuseSampler = sampler_state
{
    Texture = <DiffuseMap>;
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = Linear;
    AddressU = Wrap;
    AddressV = Wrap;
};

// Tangent-space normal in rgb, specular mask in a.
texture2D NormalMap;
sampler NormalSampler = sampler_state
{
    Texture = <NormalMap>;
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = Linear;
    AddressU = Wrap;
    AddressV = Wrap;
};

struct LitVSOut
{
    float4 pos : SV_Position;
    float3 normal : TEXCOORD0;
    float2 uv : TEXCOORD1;
    float height : TEXCOORD2;
    float3 world : TEXCOORD3;
};

LitVSOut LitVertex(float3 pos, float3 normal, float2 uv)
{
    LitVSOut o;
    float4 world = mul(float4(pos, 1.0), WorldMat);
    o.pos = mul(world, ViewProjectionMat);
    o.normal = mul(float4(normal, 0.0), WorldMat).xyz;
    o.uv = uv;
    o.height = pos.y;
    o.world = world.xyz;
    return o;
}

float3 CameraPos()
{
    return float3(ViewInverseTransposeMat._m03, ViewInverseTransposeMat._m13, ViewInverseTransposeMat._m23);
}

// The tangent frame from screen-space derivatives of position and uv, so meshes need no tangents (and baked vertex
// animation keeps working).
float3 PerturbNormal(float3 n, float3 world, float2 uv, float3 mapped)
{
    float3 dp1 = ddx(world), dp2 = ddy(world);
    float2 duv1 = ddx(uv), duv2 = ddy(uv);
    float3 dp2perp = cross(dp2, n), dp1perp = cross(n, dp1);
    float3 t = dp2perp * duv1.x + dp1perp * duv2.x;
    float3 b = dp2perp * duv1.y + dp1perp * duv2.y;
    float inv = rsqrt(max(max(dot(t, t), dot(b, b)), 1e-12));
    // Mesh uvs are stored with v flipped, so the bitangent runs the other way.
    return normalize(t * inv * mapped.x - b * inv * mapped.y + n * mapped.z);
}

float3 LitColor(LitVSOut i)
{
    float3 n = normalize(i.normal);
    float4 nm = tex2D(NormalSampler, i.uv);
    float3 mapped = nm.xyz * 2.0 - 1.0;
    mapped.xy *= Surface.x;
    n = PerturbNormal(n, i.world, i.uv, normalize(mapped));
    float3 albedo = tex2D(DiffuseSampler, i.uv).rgb;
    float3 v = normalize(CameraPos() - i.world);
    float3 l = normalize(LightDir.xyz);
    float hemi = n.y * 0.5 + 0.5;
    float3 ambient = lerp(GroundColor.rgb, SkyColor.rgb, hemi);
    float key = saturate(dot(n, l));
    float rim = pow(1.0 - saturate(dot(n, v)), 3.0) * Surface.w;
    // Sampled a little out along the normal, so wall faces read the room side of their own footprint.
    float2 lm = (i.world.xz + n.xz * 0.3 - LightMapRect.xy) * LightMapRect.zw;
    float3 torch = tex2D(LightMapSampler, lm).rgb * LightScale.x;
    float3 torchLit = torch * (0.55 + 0.45 * saturate(n.y));
    float gloss = nm.a * Surface.y;
    float specKey = pow(saturate(dot(n, normalize(l + v))), Surface.z) * key;
    float specTorch = pow(saturate(dot(n, normalize(float3(0.0, 1.0, 0.0) + v))), Surface.z * 0.5);
    float3 spec = gloss * (KeyColor.rgb * specKey + torch * specTorch * 0.8);
    float3 lit = albedo * (ambient + KeyColor.rgb * key + torchLit) + RimColor.rgb * rim * (albedo + 0.15) + spec;
    float ao = lerp(1.0 - Occlusion.x, 1.0, saturate((i.height - Occlusion.y) / Occlusion.z));
    return lerp(lit * ao, albedo * (1.0 + Emissive.y), Emissive.x);
}
