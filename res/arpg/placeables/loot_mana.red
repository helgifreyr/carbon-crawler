type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/loot.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/texmesh.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "LightMapRect"
                    value: [-34.000, -26.000, 0.003, 0.019]
                -   type: Tr2Vector4Parameter
                    name: "LightScale"
                    value: [1.500, 0.000, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/palette_loot_mana.png"
                -   type: TriTextureParameter
                    name: "LightMap"
                    resourcePath: "res:/arpg/textures/torchlight.png"
                -   type: TriTextureParameter
                    name: "NormalMap"
                    resourcePath: "res:/arpg/textures/flat_n.png"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/loot_glow.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/texmesh.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "Emissive"
                    value: [1.000, 0.400, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "LightMapRect"
                    value: [-34.000, -26.000, 0.003, 0.019]
                -   type: Tr2Vector4Parameter
                    name: "LightScale"
                    value: [1.500, 0.000, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/palette_loot_mana.png"
                -   type: TriTextureParameter
                    name: "LightMap"
                    resourcePath: "res:/arpg/textures/torchlight.png"
                -   type: TriTextureParameter
                    name: "NormalMap"
                    resourcePath: "res:/arpg/textures/flat_n.png"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/loot_halo.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/halo.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "HaloColor"
                    value: [0.300, 0.500, 1.000, 0.800]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/shadow.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/blob.fx"
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/blob.png"
