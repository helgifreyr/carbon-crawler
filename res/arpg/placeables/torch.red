type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/torch.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/texmesh.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "LightMapRect"
                    value: [-32.000, -22.000, 0.016, 0.023]
                -   type: Tr2Vector4Parameter
                    name: "LightScale"
                    value: [1.500, 0.000, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/palette_enemy.png"
                -   type: TriTextureParameter
                    name: "LightMap"
                    resourcePath: "res:/arpg/textures/torchlight.png"
                -   type: TriTextureParameter
                    name: "NormalMap"
                    resourcePath: "res:/arpg/textures/flat_n.png"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/torch_glow.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/texmesh.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "Emissive"
                    value: [1.000, 0.600, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "LightMapRect"
                    value: [-32.000, -22.000, 0.016, 0.023]
                -   type: Tr2Vector4Parameter
                    name: "LightScale"
                    value: [1.500, 0.000, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/palette_enemy.png"
                -   type: TriTextureParameter
                    name: "LightMap"
                    resourcePath: "res:/arpg/textures/torchlight.png"
                -   type: TriTextureParameter
                    name: "NormalMap"
                    resourcePath: "res:/arpg/textures/flat_n.png"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/fx_flame24.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/fx_flame.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "FxTime"
                    value: [0.000, 1.000, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxColor"
                    value: [1.000, 0.620, 0.220, 1.600]
                -   type: Tr2Vector4Parameter
                    name: "FxColorEnd"
                    value: [0.900, 0.180, 0.030, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "FxSize"
                    value: [0.260, 0.070, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxFlame"
                    value: [0.550, 0.080, 2.200, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/torch_halo.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/halo.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "HaloColor"
                    value: [1.000, 0.550, 0.200, 0.700]
                -   type: Tr2Vector4Parameter
                    name: "HaloFacing"
                    value: [1.000, 0.000, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
