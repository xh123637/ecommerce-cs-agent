const { request } = require('../../utils/request')

Page({
  data: {
    form: { title: '', description: '', category: '其他', priority: '中' }
  },
  onInput(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ [`form.${key}`]: e.detail.value })
  },
  async onSubmit() {
    const { form } = this.data
    if (!form.title || !form.description) {
      wx.showToast({ title: '请填写完整', icon: 'none' })
      return
    }
    await request('/tickets', 'POST', form)
    wx.showToast({ title: '提交成功' })
    wx.navigateBack()
  }
})
