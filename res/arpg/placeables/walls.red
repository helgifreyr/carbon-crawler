type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/walls.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/wall.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "SeeThrough"
                    value: [0.000, -1000.000, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "EyePos"
                    value: [0.000, 0.000, 0.000, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "Surface"
                    value: [1.000, 0.400, 16.000, 0.250]
                -   type: Tr2Vector4Parameter
                    name: "LightMapRect"
                    value: [-32.000, -24.000, 0.003, 0.021]
                -   type: Tr2Vector4Parameter
                    name: "LightScale"
                    value: [1.500, 0.000, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/wall.png"
                -   type: TriTextureParameter
                    name: "LightMap"
                    resourcePath: "res:/arpg/textures/torchlight.png"
                -   type: TriTextureParameter
                    name: "NormalMap"
                    resourcePath: "res:/arpg/textures/wall_n.png"
