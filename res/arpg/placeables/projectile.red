type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/projectile_glow.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/texmesh.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "Emissive"
                    value: [0.800, 0.450, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "LightMapRect"
                    value: [-34.000, -26.000, 0.003, 0.019]
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
        geometryResPath: "res:/arpg/meshes/projectile_halo.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/halo.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "HaloColor"
                    value: [1.000, 0.450, 0.120, 0.900]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/fx_trail28.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/fx_trail.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "FxTime"
                    value: [0.000, 1.000, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxColor"
                    value: [1.000, 0.550, 0.150, 2.400]
                -   type: Tr2Vector4Parameter
                    name: "FxColorEnd"
                    value: [0.600, 0.120, 0.020, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "FxSize"
                    value: [0.320, 0.080, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxTrail"
                    value: [2.000, 0.200, 4.000, 30.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
