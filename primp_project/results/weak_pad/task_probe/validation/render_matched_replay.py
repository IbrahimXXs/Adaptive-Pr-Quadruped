"""Render a preselected capacity/seed pair without rerunning any simulation.

Reuses the preserved V2 evidence renderer with a scoped presentation wrapper.
The two videos have a shared simulation clock. If a trial finishes sooner,
the combined video explicitly labels its held final frame.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

os.environ.setdefault('MUJOCO_GL', 'egl')
import cv2
import numpy as np


STUDY = Path(__file__).resolve().parent.parent
PROJECT = STUDY.parents[2]
OLD_RENDERER = PROJECT/'results/weak_pad/study_v2/validation/render_evidence_replay.py'
LABELS = {'fixed_force': 'FIXED TEST SELECTED ON DEVELOPMENT', 'task_sufficient': 'TASK-DERIVED SUFFICIENT TEST'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def legacy_renderer():
    spec = importlib.util.spec_from_file_location('legacy_evidence_renderer', OLD_RENDERER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_one(run, output, *, start_s, fps, preview_only=False):
    run = Path(run)
    metadata = json.loads((run/'metadata.json').read_text())
    with np.load(run/'signals.npz', allow_pickle=False) as archive:
        commands = archive['achieved_probe_command_n'].copy()
        targets = archive['minimum_sufficient_probe_load_n'].copy()
    policy = metadata['probe_policy']
    task_mm = 1000.*metadata['movement_optimizer_settings']['forward_progress_m']
    legacy = legacy_renderer()
    replay = legacy.replay
    previous_overlay, previous_render = replay._overlay, replay.render_replay

    def overlay(frame, index, states, meta, truth):
        frame = previous_overlay(frame, index, states, meta, truth)
        cv2.rectangle(frame, (0,0), (frame.shape[1],102), (244,246,248), -1)
        failed = bool(states['pad_failed'][index])
        sink = max(0.,1000.*float(states['pad_sink_displacement_m'][index]))
        measured_target = f'{targets[index]:.2f} N' if targets[index] > 0. else 'not planned yet'
        lines = [
            (LABELS[policy]+'  |  RECORDED SIMULATION', 27, .57),
            (f"t = {states['time_s'][index]:.2f} s   phase: {states['phase'][index]}"
             f"   task: {task_mm:g} mm   capacity: {truth['failure_load_n']:g} N (evaluation only)", 55, .46),
            (f"Pad: {'FAILED' if failed else 'INTACT'}  sink: {sink:.1f} mm"
             f"   probe target: {commands[index]:.2f} N"
             f"   needed measured plateau: {measured_target}", 84, .48),
        ]
        for line, y, scale in lines:
            cv2.putText(frame, line, (16,y), cv2.FONT_HERSHEY_SIMPLEX, scale, (37,43,49), 1, cv2.LINE_AA)
        return frame

    def render(*args, **kwargs):
        kwargs.update(output=output, start_s=start_s, fps=fps)
        return previous_render(*args, **kwargs)

    replay._overlay, replay.render_replay = overlay, render
    try:
        result = legacy.render(run, preview_only=preview_only)
    finally:
        replay._overlay, replay.render_replay = previous_overlay, previous_render
    result.update(probe_policy=policy, policy_label=LABELS[policy],
        forward_task_m=metadata['movement_optimizer_settings']['forward_progress_m'],
        hidden_capacity_n=metadata['evaluation'].get('failure_threshold_n',metadata['evaluation'].get('failure_load_n')),
        capacity_evaluator_only=True, wrapper_sha256=sha(__file__), legacy_renderer_sha256=sha(OLD_RENDERER))
    output.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def combine(left, right, output):
    videos = [cv2.VideoCapture(row['video']) for row in (left,right)]
    fps = float(left['fps'])
    if right['fps'] != left['fps'] or left['recorded_start_time_s'] != right['recorded_start_time_s']:
        raise ValueError('Paired videos must have the same frame rate and first recorded timestamp')
    counts = [row['frame_count'] for row in (left,right)]
    writer = None
    for codec in ('avc1','mp4v'):
        writer = cv2.VideoWriter(str(output),cv2.VideoWriter_fourcc(*codec),fps,(1920,720))
        if writer.isOpened():
            break
        writer.release()
    if writer is None or not writer.isOpened():
        raise RuntimeError('No paired replay encoder available')
    last = [None,None]
    try:
        for index in range(max(counts)):
            frames = []
            for side, video in enumerate(videos):
                if index < counts[side]:
                    ok, frame = video.read()
                    if not ok:
                        raise RuntimeError('Individual replay ended before its declared frame count')
                    last[side] = frame
                frame = last[side].copy()
                if index >= counts[side]:
                    cv2.rectangle(frame,(0,625),(960,675),(244,246,248),-1)
                    cv2.putText(frame,'RECORDED TRIAL COMPLETE: final frame held',(16,656),
                        cv2.FONT_HERSHEY_SIMPLEX,.61,(37,43,49),1,cv2.LINE_AA)
                frames.append(frame)
            writer.write(np.concatenate(frames,axis=1))
    finally:
        writer.release()
        for video in videos:
            video.release()
    count = 0
    decoder = cv2.VideoCapture(str(output))
    while True:
        ok, frame = decoder.read()
        if not ok:
            break
        if frame.shape != (720,1920,3):
            raise RuntimeError('Paired video has unexpected frame dimensions')
        count += 1
    decoder.release()
    if count != max(counts):
        raise RuntimeError('Paired replay failed full decode validation')
    poster = np.concatenate([cv2.imread(row['preview']) for row in (left,right)],axis=1)
    if not cv2.imwrite(str(output.with_suffix('.png')),poster):
        raise RuntimeError('Could not write paired preview')
    return dict(video=str(output),preview=str(output.with_suffix('.png')),video_sha256=sha(output),
        fps=fps,frame_count=count,resolution=[1920,720],all_frames_decoded=True,
        left_policy=left['probe_policy'],right_policy=right['probe_policy'],
        shared_start_time_s=left['recorded_start_time_s'],
        shorter_trial_presentation='Hold the final recorded frame with an explicit trial-complete label.',
        preview_presentation='Two representative outcome frames, each labeled with its own recorded timestamp.',
        source_videos=[left['video_sha256'],right['video_sha256']])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',default='progress36_capacity51p5')
    parser.add_argument('--seed',type=int,default=311)
    parser.add_argument('--start',type=float,default=28.)
    args = parser.parse_args()
    state=json.loads((STUDY/'study_state.json').read_text())
    media=STUDY/'media';media.mkdir(parents=True,exist_ok=True)
    individual=[]
    for policy in ('fixed_force','task_sufficient'):
        trial_id=f'{args.case}_{policy}_seed{args.seed}'
        entry=state['trials'][trial_id]
        if entry['status']!='completed':
            raise ValueError('Both preselected formal trials must be complete before rendering')
        output=media/f'{args.case}_{policy}_seed{args.seed}.mp4'
        row=render_one(entry['run_dir'],output,start_s=args.start,fps=20)
        row.update(trial_id=trial_id,outcome=entry['outcome'])
        individual.append(row)
    paired=combine(*individual,media/f'{args.case}_paired_seed{args.seed}.mp4')
    result=dict(case_id=args.case,seed=args.seed,individual=individual,paired=paired,
        method='Only recorded qpos/qvel and pad deformation are rendered; no controller or simulation step is run.',
        selection='The 36 mm task, 51.5 N capacity, seed 311 pair was chosen before formal recordings completed.',
        source_sha256=sha(__file__))
    (media/'index.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Matched testing-policy replay','',
        f"Preselected condition: **{1000.*individual[0]['forward_task_m']:g} mm forward task, {individual[0]['hidden_capacity_n']:g} N hidden capacity, seed {args.seed}**. Capacity is shown only as evaluation truth.",
        '',f"[Watch the synchronized comparison]({Path(paired['video']).name}) · [Preview]({Path(paired['preview']).name})",'',
        '| Policy | Recorded outcome | Individual replay |', '| --- | --- | --- |']
    for row in individual:
        lines.append(f"| {LABELS[row['probe_policy']].title()} | {row['outcome']} | [Video]({Path(row['video']).name}) |")
    lines+=['',
        'The videos restore recorded robot states and pad displacement. They do not rerun physics or control.',
        'Both panels start at the same recorded simulation time. A shorter completed trial remains on its final frame with an explicit label.',
        'The preview combines representative outcome frames; their separately labeled timestamps can differ.',
        '',
        'Overlays distinguish the selected probe command, sufficient measured plateau, actual target-pad force, certificate, and installed MPC cap.',
        'Body progress is measured from the first probing position; stronger probing does not reset the task origin.',
        '',
        'Only completed forward motion together with lifting the next leg counts as task completion. Recovery from a failed pad remains a damaged, incomplete task.',
        '',
        'The fixed command was selected on both 34 mm and 45 mm development tasks and remains one constant throughout evaluation.',
        '',
        '[Full comparison results](../../../../docs/results/task_probe.md) · [Replay provenance and complete decode checks](index.json)',
        '']
    (media/'README.md').write_text('\n'.join(lines))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
