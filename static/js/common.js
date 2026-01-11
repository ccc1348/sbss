/**
 * 共用工具函式
 */

// ========== 設備管理 ==========
function deviceBar() {
    return {
        devices: [],
        selected: '',
        status: '',
        statusClass: '',
        loading: true,

        async init() {
            await this.refresh();
        },

        async refresh() {
            this.loading = true;
            this.status = '';
            this.statusClass = '';

            try {
                const res = await fetch('/api/devices');
                const data = await res.json();
                this.devices = data.devices || [];

                if (this.devices.length === 0) {
                    this.status = '請開啟模擬器';
                    this.statusClass = 'disconnected';
                } else {
                    // 恢復上次選擇
                    const saved = localStorage.getItem('selectedDevice');
                    if (saved && this.devices.some(d => d.id === saved)) {
                        this.selected = saved;
                    } else {
                        this.selected = this.devices[0].id;
                    }
                    this.save();
                    this.status = '已連線';
                    this.statusClass = 'connected';
                }
            } catch (e) {
                this.status = '連線錯誤';
                this.statusClass = 'disconnected';
            }

            this.loading = false;
        },

        save() {
            if (this.selected) {
                localStorage.setItem('selectedDevice', this.selected);
            }
        },

        get() {
            return localStorage.getItem('selectedDevice') || '';
        }
    };
}

// ========== 模態框管理 ==========
function modal(name) {
    return {
        show: false,
        data: {},

        open(data = {}) {
            this.data = data;
            this.show = true;
            this.$nextTick(() => {
                const input = this.$refs.input;
                if (input) {
                    input.focus();
                    input.select();
                }
            });
        },

        close() {
            this.show = false;
            this.data = {};
        },

        backdropClick(e) {
            if (e.target === e.currentTarget) {
                this.close();
            }
        }
    };
}

// ========== Toast 通知 ==========
function toast() {
    return {
        visible: false,
        message: '',

        show(msg, duration = 2000) {
            this.message = msg;
            this.visible = true;
            setTimeout(() => {
                this.visible = false;
            }, duration);
        }
    };
}

// ========== API 工具 ==========
const api = {
    async get(url) {
        const res = await fetch(url);
        return res.json();
    },

    async post(url, data = {}) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },

    async delete(url) {
        const res = await fetch(url, { method: 'DELETE' });
        return res.json();
    }
};

// ========== 心跳 ==========
function startHeartbeat() {
    setInterval(() => fetch('/api/heartbeat', { method: 'POST' }), 2000);
}

// 頁面載入時啟動心跳
document.addEventListener('DOMContentLoaded', startHeartbeat);

// ========== 工具函式 ==========
function getSelectedDevice() {
    return localStorage.getItem('selectedDevice') || '';
}
