#!/usr/bin/env python3
"""Deployment-side Isaac rehearsal for exported blind-history bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--bundle-dir", required=True)
parser.add_argument("--task", required=True)
parser.add_argument("--num-envs", type=int, default=16)
parser.add_argument(
    "--max-steps",
    type=int,
    default=0,
    help="Maximum control steps before exit. Use 0 (default) to run until interrupted.",
)
parser.add_argument("--seed", type=int, default=999)
parser.add_argument("--json-out", type=str, default=None)
parser.add_argument("--command-x", type=float, default=None)
parser.add_argument("--command-y", type=float, default=None)
parser.add_argument("--command-yaw", type=float, default=None)
parser.add_argument("--compare-source", action="store_true")
parser.add_argument("--teleop", action="store_true", help="Use keyboard teleop to stream base velocity commands.")
parser.add_argument("--teleop-max-lin-x", type=float, default=0.8)
parser.add_argument("--teleop-max-lin-y", type=float, default=0.3)
parser.add_argument("--teleop-max-yaw", type=float, default=0.6)

try:
    from isaaclab.app import AppLauncher
except ModuleNotFoundError as exc:
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        parser.print_help()
        print("\nIsaacLab launcher arguments are available when this script runs under IsaacLab.")
        raise SystemExit(0) from exc
    raise SystemExit(
        "IsaacLab is required for deploy-side rehearsal. Run with:\n"
        "  bash scripts/isaaclab_user.sh -p scripts/deploy/play_deploy_policy.py ..."
    ) from exc

AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch

repo_root = Path(__file__).resolve().parents[2]
repo_root_str = str(repo_root)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

from deploy_blind_history_policy import build_deployable_module, load_checkpoint_state
from go2_deploy_contract import BLIND_HISTORY_OBSERVATION_GROUPS
from isaaclab_tasks.utils.parse_cfg import load_cfg_from_registry
import isaaclab_tasks  # noqa: F401
import go2_rough  # noqa: F401


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _unwrap_obs(obs):
    if isinstance(obs, tuple):
        return obs[0]
    return obs


def _step_env(env, actions):
    step_out = env.step(actions)
    if len(step_out) == 5:
        obs, rewards, terminated, truncated, infos = step_out
        dones = terminated | truncated
        return obs, rewards, dones, infos
    if len(step_out) == 4:
        obs, rewards, dones, infos = step_out
        return obs, rewards, dones, infos
    raise RuntimeError(f"Unexpected env.step output length: {len(step_out)}")


def _find_artifact(bundle_dir: Path, manifest: dict, suffix: str) -> Path:
    for artifact in manifest.get("exported_artifacts", []):
        if artifact.endswith(suffix):
            artifact_path = bundle_dir / artifact
            if artifact_path.exists():
                return artifact_path
    raise SystemExit(f"Could not find an artifact ending with {suffix!r} in {bundle_dir}")


def _make_command_tensor(torch_module, device, num_envs: int, command_xyz: tuple[float, float, float]):
    command_tensor = torch_module.zeros((num_envs, 3), device=device, dtype=torch_module.float32)
    command_tensor[:, 0] = command_xyz[0]
    command_tensor[:, 1] = command_xyz[1]
    command_tensor[:, 2] = command_xyz[2]
    return command_tensor


def _set_base_velocity_command(env, torch_module, command_xyz: tuple[float, float, float]) -> None:
    cmd_manager = env.unwrapped.command_manager
    command_tensor = _make_command_tensor(
        torch_module,
        env.unwrapped.device,
        env.unwrapped.num_envs,
        command_xyz,
    )
    if hasattr(cmd_manager, "set_command"):
        cmd_manager.set_command("base_velocity", command_tensor)
        return
    current = cmd_manager.get_command("base_velocity")
    if current.shape[1] < 3:
        raise RuntimeError(f"base_velocity command has unexpected shape {tuple(current.shape)}")
    current[:, :3] = command_tensor


class KeyboardTeleopController:
    """Version-robust keyboard teleop built directly on IsaacSim keyboard events."""

    def __init__(self) -> None:
        try:
            import carb
            import omni.appwindow as appwindow
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "Keyboard teleop requested, but IsaacSim keyboard APIs (carb/omni.appwindow) are unavailable."
            ) from exc

        self._carb = carb
        app_window = appwindow.get_default_app_window()
        if app_window is None:
            raise SystemExit("Keyboard teleop requested, but no default IsaacSim app window was found.")

        keyboard = app_window.get_keyboard()
        if keyboard is None:
            raise SystemExit("Keyboard teleop requested, but IsaacSim keyboard device was not found.")

        self._input = carb.input.acquire_input_interface()
        self._keyboard = keyboard
        self._pressed: set[Any] = set()
        self._subscription = self._input.subscribe_to_keyboard_events(self._keyboard, self._on_keyboard_event)

    def _on_keyboard_event(self, event, *_) -> bool:
        keyboard_event_type = self._carb.input.KeyboardEventType
        if event.type in (keyboard_event_type.KEY_PRESS, keyboard_event_type.KEY_REPEAT):
            self._pressed.add(event.input)
        elif event.type == keyboard_event_type.KEY_RELEASE:
            self._pressed.discard(event.input)
        return True

    def advance(self) -> tuple[float, float, float]:
        key = self._carb.input.KeyboardInput

        forward = float((key.W in self._pressed) or (key.UP in self._pressed))
        backward = float((key.S in self._pressed) or (key.DOWN in self._pressed))
        left_strafe = float(key.A in self._pressed)
        right_strafe = float(key.D in self._pressed)
        yaw_left = float((key.LEFT in self._pressed) or (key.Q in self._pressed))
        yaw_right = float((key.RIGHT in self._pressed) or (key.E in self._pressed))

        vx = forward - backward
        vy = left_strafe - right_strafe
        yaw = yaw_left - yaw_right
        return (vx, vy, yaw)

    def close(self) -> None:
        if self._subscription is not None:
            if hasattr(self._input, "unsubscribe_to_keyboard_events"):
                self._input.unsubscribe_to_keyboard_events(self._keyboard, self._subscription)
            elif hasattr(self._input, "unsubscribe_from_keyboard_events"):
                self._input.unsubscribe_from_keyboard_events(self._keyboard, self._subscription)
            self._subscription = None


def _configure_keyboard_teleop():
    return KeyboardTeleopController()


def main() -> int:
    bundle_dir = Path(args_cli.bundle_dir).expanduser().resolve()
    manifest_path = bundle_dir / "bundle_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing bundle manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    groups = manifest.get("deployable_observation_groups")
    if groups != BLIND_HISTORY_OBSERVATION_GROUPS:
        raise SystemExit(
            f"Unsupported deployable observation contract: {groups}. "
            f"Expected {BLIND_HISTORY_OBSERVATION_GROUPS}."
        )
    policy_path = _find_artifact(bundle_dir, manifest, ".torchscript.pt")
    deploy_cfg = json.loads(_find_artifact(bundle_dir, manifest, ".deploy_config.json").read_text())
    policy_history_length = int(deploy_cfg["observations"]["policy_history_length"])

    env_cfg = load_cfg_from_registry(args_cli.task, "env_cfg_entry_point")
    env_cfg.scene.num_envs = args_cli.num_envs
    env_cfg.seed = args_cli.seed
    if args_cli.teleop and (
        args_cli.command_x is not None or args_cli.command_y is not None or args_cli.command_yaw is not None
    ):
        raise SystemExit("Use either fixed --command-* flags or --teleop, not both.")

    if args_cli.teleop and args_cli.num_envs != 1:
        raise SystemExit("--teleop currently supports only --num-envs 1.")

    if (
        args_cli.command_x is not None
        or args_cli.command_y is not None
        or args_cli.command_yaw is not None
        or args_cli.teleop
    ):
        cmd = env_cfg.commands.base_velocity
        if args_cli.teleop:
            cmd.ranges.lin_vel_x = (0.0, 0.0)
            cmd.ranges.lin_vel_y = (0.0, 0.0)
            cmd.ranges.ang_vel_z = (0.0, 0.0)
            cmd.ranges.heading = (0.0, 0.0)
        else:
            if args_cli.command_x is not None:
                cmd.ranges.lin_vel_x = (args_cli.command_x, args_cli.command_x)
            if args_cli.command_y is not None:
                cmd.ranges.lin_vel_y = (args_cli.command_y, args_cli.command_y)
            if args_cli.command_yaw is not None:
                cmd.ranges.ang_vel_z = (args_cli.command_yaw, args_cli.command_yaw)
        cmd.resampling_time_range = (1.0e9, 1.0e9)
        cmd.rel_standing_envs = 0.0
        cmd.rel_heading_envs = 0.0
        cmd.heading_command = False

    env = None
    keyboard = None
    try:
        env = gym.make(args_cli.task, cfg=env_cfg, render_mode=None)
        print(
            f"[INFO] Deploy play env initialized: task={args_cli.task}, "
            f"num_envs={env.unwrapped.num_envs}, seed={args_cli.seed}"
        )
        device = env.unwrapped.device
        policy = torch.jit.load(str(policy_path), map_location=device)
        policy.eval()

        source_policy = None
        if args_cli.compare_source:
            source_policy = build_deployable_module(
                state_dict=load_checkpoint_state(Path(manifest["source_checkpoint"]).expanduser()),
                policy_obs_dim=int(deploy_cfg["observations"]["policy_dim"]),
                policy_history_length=policy_history_length,
            ).to(device)
            source_policy.eval()

        obs = _unwrap_obs(env.reset())
        commanded = (0.0, 0.0, 0.0)
        if args_cli.teleop:
            keyboard = _configure_keyboard_teleop()
            print(
                "Keyboard teleop enabled: W/S or Up/Down = forward/back, A/D = strafe, "
                "Left/Right or Q/E = yaw."
            )
            _set_base_velocity_command(env, torch, commanded)

        reward_sum = torch.zeros(env.unwrapped.num_envs, device=device)
        done_count = 0
        action_abs_max = 0.0
        source_export_abs_diff_max = 0.0
        source_export_abs_diff_mean_sum = 0.0
        diff_samples = 0

        step_count = 0
        while args_cli.max_steps <= 0 or step_count < args_cli.max_steps:
            if keyboard is not None:
                command_now = keyboard.advance()
                if command_now is not None:
                    commanded = (
                        _clamp(float(command_now[0]), -args_cli.teleop_max_lin_x, args_cli.teleop_max_lin_x),
                        _clamp(float(command_now[1]), -args_cli.teleop_max_lin_y, args_cli.teleop_max_lin_y),
                        _clamp(float(command_now[2]), -args_cli.teleop_max_yaw, args_cli.teleop_max_yaw),
                    )
                _set_base_velocity_command(env, torch, commanded)

            policy_obs = obs["policy"]
            history_obs = obs["policy_history"]
            with torch.inference_mode():
                actions = policy(policy_obs, history_obs)
                if source_policy is not None:
                    source_actions = source_policy(policy_obs, history_obs)
                    diff = (source_actions - actions).abs()
                    source_export_abs_diff_max = max(source_export_abs_diff_max, float(diff.max().item()))
                    source_export_abs_diff_mean_sum += float(diff.mean().item())
                    diff_samples += 1
            action_abs_max = max(action_abs_max, float(actions.abs().max().item()))
            obs, rewards, dones, _infos = _step_env(env, actions)
            obs = _unwrap_obs(obs)
            reward_sum += rewards
            done_count += int(dones.sum().item())
            step_count += 1

        report = {
            "status": "ok",
            "bundle_dir": str(bundle_dir),
            "task": args_cli.task,
            "num_envs": args_cli.num_envs,
            "max_steps": args_cli.max_steps,
            "executed_steps": step_count,
            "mean_reward_sum": float(reward_sum.mean().item()),
            "done_count": done_count,
            "action_abs_max": action_abs_max,
            "compare_source": bool(source_policy is not None),
            "source_export_abs_diff_max": source_export_abs_diff_max if source_policy is not None else None,
            "source_export_abs_diff_mean": (
                source_export_abs_diff_mean_sum / diff_samples if source_policy is not None and diff_samples else None
            ),
        }
        if args_cli.json_out:
            Path(args_cli.json_out).expanduser().resolve().write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    finally:
        if keyboard is not None and hasattr(keyboard, "close"):
            keyboard.close()
        if env is not None:
            env.close()
        simulation_app.close()


if __name__ == "__main__":
    raise SystemExit(main())
