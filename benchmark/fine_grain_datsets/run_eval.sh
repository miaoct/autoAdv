
echo "Evaluating Inception v3 on Oxford Flowers."
CUDA_VISIBLE_DEVICES=8 python eval.py --model_name="inception_v3" \
  --checkpoint_path="/home/haojieyuan/autoAdv/benchmark/fine_grain_datsets/ckpts/oxfordFlowers/model.ckpt-2000" \
  --batch_size=50 \
  --dataset_name="oxfordFlowers" \
  --num_classes=102


echo "Evaluating Inception v3 on FGVC Aircraft."
CUDA_VISIBLE_DEVICES=8 python eval.py --model_name="inception_v3" \
  --checkpoint_path="/home/haojieyuan/autoAdv/benchmark/fine_grain_datsets/ckpts/fgvcAircraft/model.ckpt-5000" \
  --batch_size=50 \
  --dataset_name="fgvcAircraft" \
  --num_classes=100

echo "Evaluating Inception v3 on Stanford Cars."
CUDA_VISIBLE_DEVICES=8 python eval.py --model_name="inception_v3" \
  --checkpoint_path="/home/haojieyuan/autoAdv/benchmark/fine_grain_datsets/ckpts/stanfordCars/model.ckpt-10000" \
  --batch_size=50 \
  --dataset_name="stanfordCars" \
  --num_classes=196