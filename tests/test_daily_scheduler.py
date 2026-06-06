from src.scheduler.daily_scheduler import DailyScheduler


def test_scheduler_initialization():
    scheduler = DailyScheduler()
    assert scheduler._scheduler is not None


def test_scheduler_has_a_share_job():
    scheduler = DailyScheduler()
    jobs = scheduler._scheduler.get_jobs()
    job_ids = [job.id for job in jobs]
    assert "a_share_daily" in job_ids


def test_scheduler_has_us_job():
    scheduler = DailyScheduler()
    jobs = scheduler._scheduler.get_jobs()
    job_ids = [job.id for job in jobs]
    assert "us_daily" in job_ids
