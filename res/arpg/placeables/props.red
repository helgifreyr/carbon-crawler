type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/props.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/texmesh.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "Occlusion"
                    value: [0.350, -0.500, 1.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "LightMapRect"
                    value: [-32.000, -24.000, 0.003, 0.021]
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
