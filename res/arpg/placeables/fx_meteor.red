type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/fx_burst80.cmf"
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
                    value: [1.000, 0.550, 0.150, 2.600]
                -   type: Tr2Vector4Parameter
                    name: "FxColorEnd"
                    value: [0.600, 0.080, 0.020, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "FxSize"
                    value: [0.500, 0.140, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxMotion"
                    value: [9.508, 2.600, -4.000, 0.500]
                -   type: Tr2Vector4Parameter
                    name: "FxShape"
                    value: [1.000, 0.400, 1.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxVary"
                    value: [0.800, 0.600, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
