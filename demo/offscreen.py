import os

import blue


class OffscreenCapture:
    """Renders the given steps into a render target and saves it, independent of window visibility."""

    def __init__(self, trinity, jobs, width, height, steps):
        self.trinity = trinity
        self.jobs = jobs
        self.target = trinity.Tr2RenderTarget(width, height, 1, trinity.PIXEL_FORMAT.B8G8R8A8_UNORM)
        depth = trinity.Tr2DepthStencil(width, height, trinity.DEPTH_STENCIL_FORMAT.D24S8, 1, 0)
        self.job = trinity.TriRenderJob()
        self.job.name = "offscreen_capture"
        for step in ([trinity.TriStepPushRenderTarget(self.target), trinity.TriStepPushDepthStencil(depth)] + list(steps)
                     + [trinity.TriStepPopDepthStencil(), trinity.TriStepPopRenderTarget()]):
            self.job.steps.append(step)
        jobs.recurring.append(self.job)

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.trinity.Tr2HostBitmap(self.target).Save(path)
        self.jobs.recurring.remove(self.job)


def capture_after(trinity, jobs, width, height, steps, path, frames=3):
    capture = OffscreenCapture(trinity, jobs, width, height, steps)
    for _ in range(frames):
        blue.synchro.Yield()
    capture.save(path)


def capture_job(trinity, job, width, height, path, frames=3):
    """Redirects an existing render job into a render target for a few frames, then saves it.

    Unlike a second job, nothing is drawn twice in a frame, which 2D text objects don't survive."""
    target = trinity.Tr2RenderTarget(width, height, 1, trinity.PIXEL_FORMAT.B8G8R8A8_UNORM)
    push, pop = trinity.TriStepPushRenderTarget(target), trinity.TriStepPopRenderTarget()
    job.steps.insert(0, push)
    job.steps.append(pop)
    for _ in range(frames):
        blue.synchro.Yield()
    job.steps.remove(push)
    job.steps.remove(pop)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    trinity.Tr2HostBitmap(target).Save(path)
