# import cv2
# from PIL import Image, ImageEnhance
# import os
#
# def enhance_image(input_path, output_path, sharpness=2.5, contrast=1.3):
#     # 读取图片
#     img = Image.open(input_path)
#     # 增强锐度
#     enhancer = ImageEnhance.Sharpness(img)
#     img = enhancer.enhance(sharpness)
#     # 增强对比度
#     enhancer = ImageEnhance.Contrast(img)
#     img = enhancer.enhance(contrast)
#     # 保存
#     img.save(output_path)
#     print(f"优化完成：{output_path}")
#
# def denoise_and_enhance(input_path, output_path):
#     # 用OpenCV去噪
#     img = cv2.imread(input_path)
#     if img is None:
#         print(f"无法读取图片: {input_path}")
#         return
#     # 双边滤波去噪，保留边缘
#     img = cv2.bilateralFilter(img, 9, 75, 75)
#     # 转为PIL增强
#     img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
#     # 锐化和对比度增强
#     enhancer = ImageEnhance.Sharpness(img_pil)
#     img_pil = enhancer.enhance(2.5)
#     enhancer = ImageEnhance.Contrast(img_pil)
#     img_pil = enhancer.enhance(1.3)
#     img_pil.save(output_path)
#     print(f"去噪+增强完成：{output_path}")
#
# if __name__ == "__main__":
#     # 你的原始二维码图片名
#     files = [
#         ("wechat.png", "wechat_optimized.png"),
#         ("alipay.png", "alipay_optimized.png")
#     ]
#     for in_name, out_name in files:
#         if os.path.exists(in_name):
#             # 先去噪再增强
#             denoise_and_enhance(in_name, out_name)
#         else:
#             print(f"未找到图片: {in_name}")


import cv2
from PIL import Image, ImageEnhance
import os


def denoise_and_enhance(input_path, output_path):
    # 检查输入文件是否存在
    if not os.path.exists(input_path):
        print(f"未找到图片: {input_path}")
        return

    # 读取图片
    img = cv2.imread(input_path)
    if img is None:
        print(f"无法读取图片: {input_path}")
        return

    # 双边滤波去噪，保留边缘
    img = cv2.bilateralFilter(img, 9, 75, 75)

    # 转换为 PIL 格式进行锐化和对比度增强
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    # 锐化和对比度增强
    enhancer = ImageEnhance.Sharpness(img_pil)
    img_pil = enhancer.enhance(2.5)
    enhancer = ImageEnhance.Contrast(img_pil)
    img_pil = enhancer.enhance(1.3)

    # 保存优化后的图片
    img_pil.save(output_path)
    print(f"去噪+增强完成：{output_path}")


# 主程序：处理图片
if __name__ == "__main__":
    # 原始二维码图片名
    files = [
        ("wechat.png", "wechat_optimized.png"),
        ("alipay.png", "alipay_optimized.png")
    ]

    for in_name, out_name in files:
        denoise_and_enhance(in_name, out_name)