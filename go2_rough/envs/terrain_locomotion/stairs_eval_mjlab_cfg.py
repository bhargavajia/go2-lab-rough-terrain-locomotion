"""Go2 terrain locomotion stairs eval configuration.

This task is intended for deploy/playback evaluation with fixed stair geometry,
while training can keep a broader curriculum in the training task.
"""

from __future__ import annotations

from isaaclab.utils import configclass

from go2_rough.envs.terrain_locomotion.stairs_mjlab_cfg import Go2TerrainLocomotionStairsEnvCfg


@configclass
class Go2TerrainLocomotionStairsEvalEnvCfg(Go2TerrainLocomotionStairsEnvCfg):
    """Eval task: force fixed 12 cm stairs for deployment-side rehearsal."""

    def __post_init__(self):
        super().__post_init__()
        terrain_gen = self.scene.terrain.terrain_generator
        for terrain_name in ("pyramid_stairs", "pyramid_stairs_inv"):
            terrain_cfg = terrain_gen.sub_terrains[terrain_name]
            terrain_cfg.step_height_range = (0.12, 0.12)
