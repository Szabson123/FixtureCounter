from locust import HttpUser, task, between

class KillAppUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def kill_app(self):
        self.client.get(
            "/api/process/kill-app/",
            params={"group": "SMT 11"},
            name="kill-app?group=SMT 11"
        )
