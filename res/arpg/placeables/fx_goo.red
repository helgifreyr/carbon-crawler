type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/fx_burst64.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/fx_burst.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "FxTime"
                    value: [0.000, 0.800, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxColor"
                    value: [0.700, 1.000, 0.250, 1.800]
                -   type: Tr2Vector4Parameter
                    name: "FxColorEnd"
                    value: [0.200, 0.400, 0.050, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "FxSize"
                    value: [0.240, 0.080, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxMotion"
                    value: [6.500, 4.500, -8.000, 0.700]
                -   type: Tr2Vector4Parameter
                    name: "FxShape"
                    value: [1.000, 0.250, 1.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
