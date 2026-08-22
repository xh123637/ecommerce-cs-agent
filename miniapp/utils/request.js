const config = require('./config')

function request(path, method = 'GET', data = {}) {
  return new Promise((resolve, reject) => {
    const token = wx.getStorageSync('token')
    wx.request({
      url: config.API_BASE_URL + path,
      method,
      data,
      header: token ? { Authorization: 'Bearer ' + token } : {},
      success: (res) => resolve(res.data),
      fail: reject
    })
  })
}

module.exports = {
  request
}
