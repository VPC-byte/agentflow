from agentflow import DAG, claude, codex, kimi


def test_airflow_like_dag_builds_dependencies():
    with DAG("demo", working_dir="/tmp/work", concurrency=2) as dag:
        plan = codex(task_id="plan", prompt="plan")
        implement = claude(task_id="implement", prompt="implement")
        review = kimi(task_id="review", prompt="review")
        merge = codex(task_id="merge", prompt="merge")
        plan >> [implement, review]
        implement >> merge
        review >> merge

    spec = dag.to_spec()
    nodes = spec.node_map
    assert spec.name == "demo"
    assert spec.working_dir == "/tmp/work"
    assert nodes["implement"].depends_on == ["plan"]
    assert nodes["review"].depends_on == ["plan"]
    assert set(nodes["merge"].depends_on) == {"implement", "review"}
