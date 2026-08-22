"""Lightweight Prometheus text metrics endpoint."""

from fastapi import APIRouter, Response

from .. import repository

router = APIRouter(tags=["metrics"])


@router.get("/api/metrics")
def metrics():
    stats = repository.ticket_stats()
    evaluation = repository.evaluation_stats()
    conversations = repository.conversation_stats()
    rlhf = repository.rlhf_stats()
    body = "\n".join(
        [
            "# HELP ecommerce_tickets_total Total tickets.",
            "# TYPE ecommerce_tickets_total gauge",
            f"ecommerce_tickets_total {stats['total']}",
            "# HELP ecommerce_tickets_resolved Resolved tickets.",
            "# TYPE ecommerce_tickets_resolved gauge",
            f"ecommerce_tickets_resolved {stats['resolved_count']}",
            "# HELP ecommerce_rlhf_records_total RLHF feedback records.",
            "# TYPE ecommerce_rlhf_records_total gauge",
            f"ecommerce_rlhf_records_total {stats['rlhf_count']}",
            "# HELP ecommerce_agent_processed_total Processed tickets by agent.",
            "# TYPE ecommerce_agent_processed_total gauge",
            f"ecommerce_agent_processed_total {evaluation['total_processed']}",
            "# HELP ecommerce_agent_avg_latency_ms Average LLM latency.",
            "# TYPE ecommerce_agent_avg_latency_ms gauge",
            f"ecommerce_agent_avg_latency_ms {evaluation['avg_llm_latency_ms'] or 0}",
            "# HELP ecommerce_agent_auto_solve_rate Auto-resolve rate.",
            "# TYPE ecommerce_agent_auto_solve_rate gauge",
            f"ecommerce_agent_auto_solve_rate {evaluation['auto_solve_rate'] or 0}",
            "# HELP ecommerce_agent_escalation_rate Human escalation rate.",
            "# TYPE ecommerce_agent_escalation_rate gauge",
            f"ecommerce_agent_escalation_rate {evaluation['human_escalation_rate'] or 0}",
            "# HELP ecommerce_rlhf_adoption_rate RLHF reply adoption rate.",
            "# TYPE ecommerce_rlhf_adoption_rate gauge",
            f"ecommerce_rlhf_adoption_rate {rlhf['adoption_rate'] or 0}",
            "# HELP ecommerce_conversations_total Multi-turn conversations.",
            "# TYPE ecommerce_conversations_total gauge",
            f"ecommerce_conversations_total {conversations['conversations']}",
            "# HELP ecommerce_conversation_messages_total Conversation messages.",
            "# TYPE ecommerce_conversation_messages_total gauge",
            f"ecommerce_conversation_messages_total {conversations['messages']}",
            "# HELP ecommerce_conversation_compactions_total Memory compactions.",
            "# TYPE ecommerce_conversation_compactions_total gauge",
            f"ecommerce_conversation_compactions_total {conversations['compactions']}",
        ]
    )
    return Response(body + "\n", media_type="text/plain; version=0.0.4")
