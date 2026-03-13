import streamlit as st
import requests
import os
import time
from dotenv import load_dotenv
from supabase import create_client

# 載入環境變數
load_dotenv()

# --- 1. 資料處理類別 (Data Logic) ---
class NovelManager:
    def __init__(self):
        self.supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        self.webhook_url = os.getenv("N8N_WEBHOOK_URL")
        self.table_name = "n8n_novel_UI"

    def get_book_list(self):
        """抓取所有不重複的小說名稱"""
        res = self.supabase.table(self.table_name).select("book_name").execute()
        return list(set([b['book_name'] for b in res.data])) if res.data else []

    def get_latest_chapter(self, book_name):
        """抓取指定小說的最新一章"""
        res = self.supabase.table(self.table_name).select("*") \
            .eq("book_name", book_name).order("chapter_no", desc=True).limit(1).execute()
        return res.data[0] if res.data else None

    def create_novel(self, name, summary, content):
        """初始化新小說 (第 0 章)"""
        data = {
            "book_name": name, 
            "chapter_no": 0, 
            "title": "設定初始化", 
            "summary": summary, 
            "content": content
        }
        return self.supabase.table(self.table_name).insert(data).execute()

    def delete_latest_chapter(self, book_name):
        """刪除最新的一章"""
        last_ch = self.supabase.table(self.table_name).select("id") \
            .eq("book_name", book_name).order("chapter_no", desc=True).limit(1).execute()
        if last_ch.data:
            self.supabase.table(self.table_name).delete().eq("id", last_ch.data[0]['id']).execute()
            return True
        return False

    def delete_full_novel(self, book_name):
        """刪除整本小說"""
        self.supabase.table(self.table_name).delete().eq("book_name", book_name).execute()
        return True

    def trigger_n8n(self, book_name):
        """觸發 n8n Webhook"""
        try:
            payload = {"book_name": book_name}
            # 設定較短的 timeout，因為我們只要觸發，後續交給 Polling
            requests.post(self.webhook_url, json=payload, timeout=5)
            return True
        except Exception as e:
            print(f"Webhook Error: {e}")
            return False

# --- 2. 介面類別 (UI Logic) ---
class NovelUI:
    def __init__(self):
        self.manager = NovelManager()
        # 初始化 Session State 防止重複觸發
        if 'is_generating' not in st.session_state:
            st.session_state.is_generating = False

    def render_sidebar(self):
        st.sidebar.header("📚 作品管理")
        
        # 1. 建立新作品
        with st.sidebar.expander("✨ 建立新小說專案"):
            with st.form("new_book"):
                n_name = st.text_input("小說名稱")
                ch0_sum = st.text_area("第 0 章核心設定 (Summary)")
                ch0_con = st.text_area("第 0 章內容 (Content)")
                if st.form_submit_button("初始化小說"):
                    if n_name and ch0_con:
                        self.manager.create_novel(n_name, ch0_sum, ch0_con)
                        st.sidebar.success(f"《{n_name}》已建立！")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("請填寫書名與內容")

        # 2. 切換作品
        options = self.manager.get_book_list()
        current_book = st.sidebar.selectbox("切換當前小說", ["請選擇"] + options)

        # 3. 危險操作區
        if current_book != "請選擇":
            st.sidebar.markdown("---")
            st.sidebar.subheader("⚠️ 危險操作")
            
            if st.sidebar.button("🗑️ 刪除最新一章"):
                if self.manager.delete_latest_chapter(current_book):
                    st.sidebar.warning("最後一章已移除")
                    time.sleep(1)
                    st.rerun()

            with st.sidebar.expander("🧨 刪除整本小說"):
                st.error("此操作將永久清空所有章節！")
                confirm = st.text_input(f"請輸入 '{current_book}' 確認刪除")
                if st.button("確認永久刪除", type="primary"):
                    if confirm == current_book:
                        self.manager.delete_full_novel(current_book)
                        st.sidebar.error("專案已刪除")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.sidebar.info("書名輸入不符")
        
        return None if current_book == "請選擇" else current_book

    def render_main(self, current_book):
        if not current_book:
            st.info("👋 請在左側選單選擇或建立一個怪談專案。")
            return

        # 抓取最新進度
        latest_data = self.manager.get_latest_chapter(current_book)
        
        if latest_data:
            st.header(f"📖 《{current_book}》")
            st.subheader(f"{latest_data['title']} (第 {latest_data['chapter_no']} 章)")
            
            with st.expander("查看當前章節摘要"):
                st.write(latest_data['summary'])
            
            st.markdown("---")
            st.write(latest_data['content'])
            st.markdown("---")

            # 生成按鈕邏輯
            if st.session_state.is_generating:
                st.button("AI 正在解析規則中...", disabled=True)
                self.handle_generation(current_book, latest_data['chapter_no'])
            else:
                if st.button("🚀 生成下一章", type="primary"):
                    st.session_state.is_generating = True
                    st.rerun()

    def handle_generation(self, book_name, current_ch):
        """處理 n8n 觸發與資料庫輪詢"""
        if self.manager.trigger_n8n(book_name):
            with st.status("🔮 正在穿越怪談領域...", expanded=True) as status:
                st.write("已傳送 Webhook 至 n8n...")
                st.write("等待 AI 構思劇情與校對規則...")
                
                # 輪詢檢查 (最多等待 180 秒)
                for i in range(90):
                    time.sleep(2)
                    check = self.manager.get_latest_chapter(book_name)
                    if check and check["chapter_no"] > current_ch:
                        status.update(label="✅ 生成成功！", state="complete", expanded=False)
                        st.session_state.is_generating = False
                        time.sleep(1)
                        st.rerun()
                        return
                
                status.update(label="❌ 等待超時", state="error")
                st.session_state.is_generating = False
        else:
            st.error("連線 n8n 失敗，請檢查網路或環境變數。")
            st.session_state.is_generating = False

# --- 3. 執行進入點 ---
if __name__ == "__main__":
    st.set_page_config(
        page_title="AI 小說家 - 怪談管理後台",
        page_icon="🕯️",
        layout="wide"
    )
    
    ui = NovelUI()
    selected_book = ui.render_sidebar()
    ui.render_main(selected_book)