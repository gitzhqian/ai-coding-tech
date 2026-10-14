// 景点历史解说技能：前端交互
(function () {
    'use strict';

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function renderList(title, items) {
        if (!items || !items.length) {
            return '';
        }
        var lis = items.map(function (item) {
            return '<li>' + escapeHtml(item) + '</li>';
        }).join('');
        return (
            '<div class="commentary-block">' +
            '<h5>' + escapeHtml(title) + '</h5>' +
            '<ul>' + lis + '</ul>' +
            '</div>'
        );
    }

    function renderCommentary(data) {
        var html = '';

        if (data.title) {
            html += '<h4 class="commentary-title">' + escapeHtml(data.title) + ' · 历史解说</h4>';
        }
        if (data.history) {
            html += '<p class="commentary-history">' + escapeHtml(data.history) + '</p>';
        }

        html += renderList('趣味典故', data.stories);
        html += renderList('必看亮点', data.highlights);
        html += renderList('游览贴士', data.tips);

        var meta = data.qwen_used
            ? 'AI 智能生成'
            : '本地解说模式（AI 暂不可用）';
        if (data.generated_at) {
            meta += ' · ' + escapeHtml(data.generated_at);
        }
        html += '<p class="commentary-meta">' + meta + '</p>';

        return html;
    }

    function requestCommentary(btn) {
        var panel = btn.parentElement.querySelector('.commentary-panel');
        if (!panel) {
            return;
        }

        if (panel.dataset.loaded === '1') {
            panel.hidden = !panel.hidden;
            btn.textContent = panel.hidden ? '景点历史解说' : '收起历史解说';
            return;
        }

        panel.hidden = false;
        panel.innerHTML = '<p class="commentary-loading">正在生成历史解说，请稍候…</p>';
        btn.disabled = true;
        btn.textContent = '生成中…';

        var payload = {
            name: btn.dataset.name || '',
            city: btn.dataset.city || '',
            type: btn.dataset.type || '',
            description: btn.dataset.description || '',
            tags: btn.dataset.tags ? btn.dataset.tags.split(',') : []
        };

        fetch('/commentary', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(function (res) {
                return res.json()
                    .catch(function () { return {}; })
                    .then(function (data) {
                        return { ok: res.ok, data: data };
                    });
            })
            .then(function (result) {
                btn.disabled = false;
                if (!result.ok) {
                    throw new Error((result.data && result.data.error) || '生成历史解说失败');
                }
                panel.innerHTML = renderCommentary(result.data);
                panel.dataset.loaded = '1';
                btn.textContent = '收起历史解说';
            })
            .catch(function (err) {
                btn.disabled = false;
                btn.textContent = '景点历史解说';
                panel.innerHTML = '<p class="commentary-error">' +
                    escapeHtml(err.message || '网络错误，请稍后重试') + '</p>';
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.btn-commentary').forEach(function (btn) {
            btn.addEventListener('click', function () {
                requestCommentary(btn);
            });
        });
    });
})();
