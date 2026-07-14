import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path

from modules.scoring import calculate\_subdomain\_scores, scores\_to\_feature\_dict, response\_quality\_checks
from modules.decision\_engine import load\_json, calculate\_cluster\_scores, attach\_confidence, detect\_uncertainties, get\_top\_clusters
from modules.charts import create\_interest\_pie\_chart, create\_work\_style\_bar\_chart, create\_cluster\_donut\_chart
from modules.reports import simple\_student\_report
from modules.pdf\_export import save\_markdown\_report

st.set\_page\_config(page\_title="Kariyer Keşif Robotu", page\_icon="🧭", layout="wide")

ITEMS\_PATH = "data/items.csv"
CAREER\_CLUSTERS\_PATH = "data/career\_clusters.json"
OUTPUT\_REPORTS\_DIR = "outputs/reports"

LIKERT\_OPTIONS = {
"Bana hiç uygun değil": 1,
"Bana biraz uygun": 2,
"Kararsızım / Bazen uygun": 3,
"Bana oldukça uygun": 4,
"Bana çok uygun": 5,
}

@st.cache\_data
def load\_items(path=ITEMS\_PATH):
try:
return pd.read\_csv(path)
except FileNotFoundError:
st.error(f"items.csv bulunamadı: {path}")
return pd.DataFrame()

@st.cache\_data
def load\_career\_clusters(path=CAREER\_CLUSTERS\_PATH):
try:
return load\_json(path)
except FileNotFoundError:
st.error(f"career\_clusters.json bulunamadı: {path}")
return {"clusters": \[]}

def init\_session\_state():
defaults = {
"step": "welcome",
"responses": {},
"student\_profile": {},
"scores\_df": None,
"feature\_scores": None,
"cluster\_results": None,
"top\_clusters": None,
"uncertainties": \[],
"quality\_checks": None,
"student\_report\_md": "",
}

```
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value
```

def go\_to(step):
st.session\_state.step = step
st.rerun()

def reset\_app():
for key in list(st.session\_state.keys()):
del st.session\_state\[key]
init\_session\_state()
st.rerun()

init\_session\_state()

st.sidebar.title("🧭 Kariyer Keşif Robotu")
st.sidebar.caption("MVP v2")

if st.sidebar.button("Başa dön"):
reset\_app()

st.sidebar.markdown("---")
st.sidebar.write(f"Aktif adım: `{st.session_state.step}`")

if st.session\_state.step == "welcome":
st.title("Kariyer Keşif Robotuna Hoş Geldin")
st.write(
"Bu sistem, ilgi alanlarını, güçlü yönlerini, çalışma tarzını ve kariyer keşif alanlarını "
"anlamana yardımcı olmak için geliştirilmiş yapay zekâ destekli bir ön danışma aracıdır."
)
st.warning("Bu sistem kesin meslek seçimi yapmaz, psikolojik tanı koymaz ve zekâ testi değildir.")

```
col1, col2 = st.columns(2)
with col1:
    if st.button("Başla", type="primary"):
        go_to("consent")
with col2:
    st.info("Devam etmeden önce bilgilendirme ve onam ekranı gösterilecektir.")
```

elif st.session\_state.step == "consent":
st.title("Onam ve Bilgilendirme")
st.write("Devam etmeden önce aşağıdaki maddeleri okuyup onaylaman gerekir.")

```
c1 = st.checkbox("Bu sistemin kesin meslek kararı vermediğini anladım.")
c2 = st.checkbox("Bu sistemin psikolojik veya klinik tanı koymadığını anladım.")
c3 = st.checkbox("Bu sistemin zekâ testi olmadığını anladım.")
c4 = st.checkbox("Yapay zekâ sonuçlarının yanılabileceğini anladım.")
c5 = st.checkbox("Verilerimin kariyer keşif profili oluşturmak amacıyla kullanılmasını kabul ediyorum.")

if st.button("Kabul Ediyorum ve Devam Et", type="primary"):
    if all([c1, c2, c3, c4, c5]):
        st.session_state.student_profile["consent"] = True
        st.session_state.student_profile["consent_timestamp"] = datetime.now().isoformat()
        go_to("profile")
    else:
        st.error("Devam etmek için tüm maddeleri onaylamalısın.")
```

elif st.session\_state.step == "profile":
st.title("Öğrenci Bilgileri")

```
nickname = st.text_input("Adın veya takma adın")
age = st.number_input("Yaş", min_value=6, max_value=25, step=1)
grade = st.selectbox("Sınıf", ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "Mezun"])
favorite_subjects = st.text_input("En sevdiğin dersler")
difficult_subjects = st.text_input("Zorlandığın dersler")
career_ideas = st.text_area("Aklından geçen meslekler veya alanlar varsa yazabilirsin")

if st.button("Devam Et", type="primary"):
    if nickname and age and grade:
        st.session_state.student_profile.update({
            "nickname": nickname,
            "age": int(age),
            "grade": grade,
            "favorite_subjects": favorite_subjects,
            "difficult_subjects": difficult_subjects,
            "career_ideas": career_ideas,
            "assessment_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        go_to("intro_chat")
    else:
        st.error("Lütfen ad/takma ad, yaş ve sınıf alanlarını doldur.")
```

elif st.session\_state.step == "intro\_chat":
st.title("Kısa Tanıma Sohbeti")
st.write("Ankete geçmeden önce seni biraz tanımak istiyorum. Kısa cevaplar verebilirsin.")

```
q1 = st.text_area("Okulda en çok hangi derslerde zaman hızlı geçiyor?")
q2 = st.text_area("Boş zamanlarında kendiliğinden ne yaparsın?")
q3 = st.text_area("Bir işle uğraşırken zamanın nasıl geçtiğini anlamadığın olur mu?")
q4 = st.text_area("Bir şeyi çözmek mi, tasarlamak mı, anlatmak mı, yönetmek mi, insanlara yardım etmek mi sana daha yakın?")

if st.button("Ankete Geç", type="primary"):
    st.session_state.student_profile["intro_chat"] = {
        "favorite_flow_subjects": q1,
        "free_time": q2,
        "flow_activity": q3,
        "preferred_activity_type": q4,
    }
    go_to("questionnaire")
```

elif st.session\_state.step == "questionnaire":
st.title("Kısa Tarama Anketi")

```
items_df = load_items()
if items_df.empty:
    st.stop()

st.write("Her ifade için sana en uygun seçeneği işaretle.")
st.caption("Burada doğru ya da yanlış cevap yoktur.")

with st.form("questionnaire_form"):
    responses = {}
    for _, item in items_df.iterrows():
        selected = st.radio(
            item["item_text"],
            list(LIKERT_OPTIONS.keys()),
            key=f"item_{item['item_id']}",
            horizontal=True,
        )
        responses[item["item_id"]] = LIKERT_OPTIONS[selected]

    submitted = st.form_submit_button("Cevapları Kaydet ve Devam Et")

if submitted:
    st.session_state.responses = responses
    st.session_state.quality_checks = response_quality_checks(responses)
    go_to("micro_tasks")
```

elif st.session\_state.step == "micro\_tasks":
st.title("Kısa Görevler")
st.write("Bu bölüm sınav değildir. Nasıl düşündüğünü anlamak için kısa görevler içerir.")

```
task_1 = st.text_area("Görev 1: Gençlerin meslekleri ve kendi yeteneklerini keşfetmesi için bir mobil uygulama tasarlasan, içinde hangi 3 özellik olurdu?")
task_2 = st.text_area("Görev 2: Bir okul kulübünde 6 öğrenci var ve herkes farklı görev yapmak istiyor. Bu ekibi nasıl organize ederdin?")

if st.button("Sonuçları Hesapla", type="primary"):
    st.session_state.student_profile["micro_tasks"] = {
        "creative_design_task": task_1,
        "team_organization_task": task_2,
    }
    go_to("calculate_results")
```

elif st.session\_state.step == "calculate\_results":
st.title("Sonuçlar Hesaplanıyor")

```
items_df = load_items()
career_clusters = load_career_clusters()

scores_df = calculate_subdomain_scores(items_df, st.session_state.responses)
if scores_df.empty:
    st.error("Sonuç hesaplanamadı. Lütfen anketi tekrar doldur.")
    st.stop()

feature_scores = scores_to_feature_dict(scores_df)
cluster_results = calculate_cluster_scores(feature_scores, career_clusters)
cluster_results = attach_confidence(cluster_results, feature_scores)
uncertainties = detect_uncertainties(feature_scores, st.session_state.quality_checks)
top_clusters = get_top_clusters(cluster_results, limit=5)

report_md = simple_student_report(st.session_state.student_profile, top_clusters, uncertainties)

st.session_state.scores_df = scores_df
st.session_state.feature_scores = feature_scores
st.session_state.cluster_results = cluster_results
st.session_state.top_clusters = top_clusters
st.session_state.uncertainties = uncertainties
st.session_state.student_report_md = report_md

go_to("results")
```

elif st.session\_state.step == "results":
st.title("Kariyer Keşif Sonuçların")

```
scores_df = st.session_state.scores_df
top_clusters = st.session_state.top_clusters
uncertainties = st.session_state.uncertainties

if scores_df is None:
    st.error("Sonuç bulunamadı. Lütfen anketi tekrar doldur.")
    st.stop()

st.write("Aşağıdaki sonuçlar kesin meslek kararı değildir. İlgi alanlarını ve keşfetmen faydalı olabilecek kariyer kümelerini gösterir.")

quality = st.session_state.quality_checks
if quality and quality.get("warnings"):
    for warning in quality["warnings"]:
        st.warning(warning)

col1, col2 = st.columns(2)

with col1:
    fig_interest = create_interest_pie_chart(scores_df)
    if fig_interest:
        st.plotly_chart(fig_interest, use_container_width=True)

with col2:
    fig_clusters = create_cluster_donut_chart(top_clusters)
    if fig_clusters:
        st.plotly_chart(fig_clusters, use_container_width=True)

fig_work = create_work_style_bar_chart(scores_df)
if fig_work:
    st.plotly_chart(fig_work, use_container_width=True)

st.subheader("Sana Yakın Görünen Kariyer Kümeleri")
if top_clusters:
    cluster_table = pd.DataFrame([
        {"Kariyer Kümesi": c["name_tr"], "Uyum": c["fit_score"], "Güven": c["confidence"]}
        for c in top_clusters
    ])
    st.table(cluster_table)

if uncertainties:
    st.subheader("Ek Veriyle Netleşmesi Faydalı Alanlar")
    for u in uncertainties:
        st.info(u.get("message_tr"))

st.warning("Bu sonuçlar ön değerlendirme niteliğindedir. Kesin meslek seçimi, psikolojik tanı veya zekâ değerlendirmesi değildir.")

col1, col2 = st.columns(2)
with col1:
    if st.button("3 Aylık Keşif Planını Gör", type="primary"):
        go_to("development_plan")
with col2:
    if st.button("Raporu Gör / İndir"):
        go_to("report")
```

elif st.session\_state.step == "development\_plan":
st.title("3 Aylık Keşif Planı")
st.write("Bu plan karar vermek için değil, deneyerek kendini tanıman için hazırlanmıştır.")

```
top_clusters = st.session_state.top_clusters or []

st.subheader("Öne Çıkan Alanlar")
for c in top_clusters[:3]:
    st.markdown(f"### {c['name_tr']}")
    for exp in c.get("recommended_experiences_tr", []):
        st.write(f"- {exp}")

st.subheader("Genel 12 Haftalık Plan")
plan = pd.DataFrame([
    {"Zaman": "1–2. hafta", "Görev": "Öne çıkan 3 kariyer alanını araştır."},
    {"Zaman": "3–4. hafta", "Görev": "Bir kulüp, atölye veya online etkinlik dene."},
    {"Zaman": "5–8. hafta", "Görev": "Küçük bir proje üret."},
    {"Zaman": "9–10. hafta", "Görev": "Bir öğretmen, uzman veya aile bireyinden geri bildirim al."},
    {"Zaman": "11–12. hafta", "Görev": "Robotla yeniden değerlendirme yap."},
])
st.table(plan)

if st.button("Sonuçlara Geri Dön"):
    go_to("results")
```

elif st.session\_state.step == "report":
st.title("Rapor")

```
report_md = st.session_state.student_report_md
if not report_md:
    st.error("Rapor oluşturulamadı.")
    st.stop()

st.markdown(report_md)

nickname = st.session_state.student_profile.get("nickname", "ogrenci")
safe_name = nickname.replace(" ", "_")
output_path = Path(OUTPUT_REPORTS_DIR) / f"{safe_name}_kariyer_raporu.md"

saved_path = save_markdown_report(report_md, output_path)

with open(saved_path, "rb") as f:
    st.download_button(
        label="Markdown Raporu İndir",
        data=f,
        file_name=f"{safe_name}_kariyer_raporu.md",
        mime="text/markdown",
    )

st.info("PDF indirme özelliği sonraki sürümde eklenecektir.")

if st.button("Sonuçlara Geri Dön"):
    go_to("results")
```

