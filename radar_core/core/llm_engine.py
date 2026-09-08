"""Hybrid Multi-Provider LLM Engine (Google Gemini + OpenAI).
Maliyet-etkin, akıllı ve kesintisiz hibrit yapay zeka yönlendiricisi:
- Haber & Bülten Analizi (news_analysis): Gemini Flash (Ücretsiz) -> Kota/Yoğunlukta GPT-4o-mini'ye Failover
- Portföy & Varlık Yönlendirmesi (portfolio_copilot): OpenAI GPT-4o-mini (Derin Mantık & Hassas Hesaplama) -> Failover Gemini Flash
- Kritik Şoklar (critical_shock): OpenAI GPT-4o -> Failover GPT-4o-mini -> Gemini Flash
"""

import json
import logging
import re
import time
from typing import Any, Literal, Type, TypeVar

from pydantic import BaseModel

from radar_core.config.settings import get_settings
from radar_core.core.models import StructuredAnalysisOutput

logger = logging.getLogger("radar_core.llm")

T = TypeVar("T", bound=BaseModel)

TaskType = Literal["news_analysis", "portfolio_copilot", "critical_shock"]


class LLMEngine:
    """Production Multi-Provider LLM Router with Cross-Provider Failover."""

    def __init__(
        self,
        gemini_api_key: str | None = None,
        openai_api_key: str | None = None,
        gemini_model: str | None = None,
        openai_model_fast: str | None = None,
        openai_model_heavy: str | None = None,
        openai_model_reasoning: str | None = None,
        max_retries: int | None = None,
        backoff_factor: float | None = None,
    ):
        settings = get_settings()

        self.gemini_api_key = gemini_api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.openai_api_key = openai_api_key or getattr(settings, "OPENAI_API_KEY", "")

        self.gemini_model = gemini_model or getattr(settings, "GEMINI_MODEL", "gemini-flash-latest")
        self.openai_model_fast = openai_model_fast or getattr(settings, "OPENAI_MODEL_FAST", "gpt-4o-mini")
        self.openai_model_heavy = openai_model_heavy or getattr(settings, "OPENAI_MODEL_HEAVY", "gpt-4o")
        self.openai_model_reasoning = openai_model_reasoning or getattr(settings, "OPENAI_MODEL_REASONING", "gpt-4o")

        self.max_retries = max_retries or getattr(settings, "MAX_RETRIES", 3)
        self.backoff_factor = backoff_factor or getattr(settings, "BACKOFF_FACTOR", 1.5)

        self._gemini_client = None
        self._openai_client = None

        self._init_clients()

    def _init_clients(self) -> None:
        if self.gemini_api_key:
            try:
                from google import genai
                from google.genai import types
                self._gemini_client = genai.Client(
                    api_key=self.gemini_api_key,
                    http_options=types.HttpOptions(timeout=12000),
                )
                logger.info("Google GenAI Client initialized (model: %s).", self.gemini_model)
            except Exception as exc:
                logger.warning("Failed initializing Google GenAI Client: %s", exc)

        if self.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=self.openai_api_key, timeout=18.0)
                logger.info("OpenAI Client initialized (models: %s / %s).", self.openai_model_fast, self.openai_model_heavy)
            except Exception as exc:
                logger.warning("Failed initializing OpenAI Client: %s", exc)

    # -----------------------------------------------------------------------
    # Zero-Cost Pre-Filtering Hook
    # -----------------------------------------------------------------------
    def pre_filter(
        self,
        text: str,
        include_keywords: list[str] | None = None,
        exclude_keywords: list[str] | None = None,
        min_length: int = 50,
    ) -> tuple[bool, str]:
        """Sıfır API maliyetiyle metni ön elemeden geçirir."""
        if not text or len(text.strip()) < min_length:
            return False, f"İçerik uzunluğu ({len(text.strip()) if text else 0}) asgari eşiğin ({min_length}) altında."

        lower_text = text.lower()

        if exclude_keywords:
            for kw in exclude_keywords:
                pattern = rf"\b{re.escape(kw.lower())}\b"
                if re.search(pattern, lower_text):
                    return False, f"Hariç tutulan anahtar kelime eşleşti: '{kw}'"

        if include_keywords:
            matched = False
            for kw in include_keywords:
                pattern = rf"\b{re.escape(kw.lower())}\b"
                if re.search(pattern, lower_text):
                    matched = True
                    break
            if not matched:
                return False, f"Zorunlu kelimelerin hiçbiri bulunamadı: {include_keywords}"

        return True, "Ön eleme başarıyla geçildi."

    # -----------------------------------------------------------------------
    # Multi-Provider Execution with Cross-Failover
    # -----------------------------------------------------------------------
    def analyze_structured(
        self,
        prompt: str,
        response_schema: Type[T] = StructuredAnalysisOutput,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        task_type: TaskType = "news_analysis",
    ) -> T:
        """
        Görevin kritiklik seviyesine göre en verimli ve akıllı sağlayıcıyı seçer:
        - news_analysis: Gemini Flash (Ücretsiz) -> Yoğunluk/Kota hatasında GPT-4o-mini'ye Failover
        - portfolio_copilot: o1 (OpenAI Flagship Derin Muhakeme Modeli) -> GPT-4o -> GPT-4o-mini -> Gemini Flash
        - critical_shock: o1 -> GPT-4o -> GPT-4o-mini -> Gemini Flash
        """
        if task_type == "news_analysis":
            provider_order = [("gemini", self.gemini_model), ("openai", self.openai_model_fast)]
        elif task_type == "portfolio_copilot":
            provider_order = [
                ("openai", self.openai_model_reasoning),
                ("openai", self.openai_model_heavy),
                ("openai", self.openai_model_fast),
                ("gemini", self.gemini_model),
            ]
        elif task_type == "critical_shock":
            provider_order = [
                ("openai", self.openai_model_reasoning),
                ("openai", self.openai_model_heavy),
                ("openai", self.openai_model_fast),
                ("gemini", self.gemini_model),
            ]
        else:
            provider_order = [("gemini", self.gemini_model), ("openai", self.openai_model_fast)]

        last_error = None

        for provider, model_name in provider_order:
            if provider == "gemini" and not self._gemini_client:
                continue
            if provider == "openai" and not self._openai_client:
                continue

            try:
                logger.info("Executing [%s] via %s (%s)...", task_type, provider.upper(), model_name)
                if provider == "gemini":
                    return self._call_gemini(prompt, response_schema, system_instruction, temperature, model_name)
                elif provider == "openai":
                    return self._call_openai(prompt, response_schema, system_instruction, temperature, model_name)
            except Exception as exc:
                logger.warning(
                    "Provider %s (%s) failed for task '%s': %s. Failing over to next provider...",
                    provider,
                    model_name,
                    task_type,
                    exc,
                )
                last_error = exc

        raise RuntimeError(f"All LLM providers failed for task '{task_type}'. Last error: {last_error}")

    # -----------------------------------------------------------------------
    # Gemini Invoker (Developer API Safe JSON Mode)
    # -----------------------------------------------------------------------
    def _call_gemini(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str | None,
        temperature: float,
        model_name: str,
    ) -> T:
        from google.genai import types

        sys_msg = (
            "Sen Türkiye ve küresel makroekonomi ve piyasa analizi uzmanı bir yapay zekasın. "
            "Yanıtını StructuredAnalysisOutput formatına uygun şekilde geçerli bir JSON objesi olarak üret.\n"
            "Zorunlu JSON anahtarları:\n"
            "- severity: 'INFO' | 'WARNING' | 'OPPORTUNITY' | 'CRITICAL'\n"
            "- summary_title: Kısa, çarpıcı Türkçe başlık (maks 110 karakter)\n"
            "- detailed_reasoning: Detaylı gerekçelendirme metni (Basitçe Ne Demek? + Teknik Analiz)\n"
            "- action_items: Yatırımcı için önerilen eylemler listesi (string array)\n"
            "- metrics: Obje { policy_stance: 'ŞAHİN'|'GÜVERCİN'|'EKSEN DEĞİŞİMİ'|'NÖTR', "
            "relevance_score: 0-100, simple_summary: string, technical_analysis: string, asset_impact: obje}\n"
            "Sadece ve sadece JSON formatında yanıt ver."
        )
        if system_instruction:
            sys_msg += f"\n\nEk Yönergeler:\n{system_instruction}"

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=sys_msg,
            temperature=temperature,
        )

        response = self._gemini_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        raw_text = response.text or "{}"
        clean_text = raw_text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
            clean_text = re.sub(r"\s*```$", "", clean_text)

        return response_schema.model_validate_json(clean_text)

    # -----------------------------------------------------------------------
    # OpenAI Invoker (Structured JSON Mode)
    # -----------------------------------------------------------------------
    def _call_openai(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str | None,
        temperature: float,
        model_name: str,
    ) -> T:
        sys_msg = (
            "Sen Türkiye ve küresel makroekonomi, para politikası ve varlık dağılımı uzmanı bir yapay zekasın. "
            "Aşağıdaki JSON anahtarlarına tam olarak uyan geçerli bir JSON nesnesi döndür:\n"
            "- severity: 'INFO' | 'WARNING' | 'OPPORTUNITY' | 'CRITICAL'\n"
            "- summary_title: Kısa, çarpıcı Türkçe başlık (maks 110 karakter)\n"
            "- detailed_reasoning: Detaylı gerekçelendirme metni (Basitçe Ne Demek? + Teknik Analiz)\n"
            "- action_items: Yatırımcı için önerilen somut eylemler listesi (string array)\n"
            "- metrics: Obje { policy_stance: 'ŞAHİN'|'GÜVERCİN'|'EKSEN DEĞİŞİMİ'|'NÖTR', "
            "relevance_score: 0-100, simple_summary: string, technical_analysis: string, asset_impact: obje}\n"
            "Sadece ve sadece geçerli JSON döndür, markdown veya ek metin ekleme."
        )
        if system_instruction:
            sys_msg += f"\n\nEk Yönergeler:\n{system_instruction}"

        is_reasoning_model = (
            any(model_name.lower().startswith(p) for p in ["o1", "o3", "o4", "o-"])
            or "reasoning" in model_name.lower()
        )
        role_name = "developer" if is_reasoning_model else "system"

        call_kwargs = {
            "model": model_name,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": role_name, "content": sys_msg},
                {"role": "user", "content": prompt},
            ],
        }

        if is_reasoning_model:
            call_kwargs["max_completion_tokens"] = 1500
            # Sınırlı muhakeme eforu: reasoning_effort='low' gizli düşünce token tüketimini minimuma indirir
            try:
                call_kwargs["reasoning_effort"] = "low"
            except Exception:
                pass
        else:
            call_kwargs["temperature"] = temperature
            call_kwargs["max_tokens"] = 1000

        response = self._openai_client.chat.completions.create(**call_kwargs)

        raw_text = response.choices[0].message.content or "{}"
        clean_text = raw_text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
            clean_text = re.sub(r"\s*```$", "", clean_text)

        return response_schema.model_validate_json(clean_text)

    # -----------------------------------------------------------------------
    # In-App Credentials & Model Connection Verifier
    # -----------------------------------------------------------------------
    @staticmethod
    def test_connection(provider: str, api_key: str, model_name: str) -> dict[str, Any]:
        """Canlı olarak API anahtarı ve model geçerliliğini test eder."""
        import time
        t0 = time.perf_counter()
        prov = provider.lower().strip()

        if not api_key:
            return {"success": False, "error": "API anahtarı boş olamaz."}

        try:
            if prov == "gemini":
                from google import genai
                from google.genai import types
                client = genai.Client(
                    api_key=api_key,
                    http_options=types.HttpOptions(timeout=10000),
                )
                res = client.models.generate_content(
                    model=model_name or "gemini-flash-latest",
                    contents="Kısa test: 1 kelimeyle 'aktif' yaz.",
                )
                latency = round((time.perf_counter() - t0) * 1000)
                reply = (res.text or "").strip()[:50]
                return {
                    "success": True,
                    "provider": "Gemini",
                    "model": model_name,
                    "latency_ms": latency,
                    "reply": reply,
                    "message": f"Gemini bağlantısı başarılı ({latency}ms)",
                }

            elif prov == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=api_key, timeout=12.0)
                is_reasoning = any(model_name.lower().startswith(p) for p in ["o1", "o3", "o4", "o-"]) or "reasoning" in model_name.lower()
                kwargs = {
                    "model": model_name or "gpt-4o",
                    "messages": [{"role": "user", "content": "Kısa test: 1 kelimeyle 'aktif' yaz."}],
                }
                if is_reasoning:
                    kwargs["max_completion_tokens"] = 50
                else:
                    kwargs["max_tokens"] = 50
                    kwargs["temperature"] = 0.1

                res = client.chat.completions.create(**kwargs)
                latency = round((time.perf_counter() - t0) * 1000)
                reply = (res.choices[0].message.content or "").strip()[:50]
                return {
                    "success": True,
                    "provider": "OpenAI",
                    "model": model_name,
                    "latency_ms": latency,
                    "reply": reply,
                    "message": f"OpenAI bağlantısı başarılı ({latency}ms)",
                }
            else:
                return {"success": False, "error": f"Bilinmeyen sağlayıcı: {provider}"}
        except Exception as exc:
            latency = round((time.perf_counter() - t0) * 1000)
            return {
                "success": False,
                "provider": provider,
                "model": model_name,
                "latency_ms": latency,
                "error": str(exc),
            }

