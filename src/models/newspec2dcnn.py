from typing import Optional
import segmentation_models_pytorch as smp
import torch
import torch.nn as nn
from torchvision.transforms.functional import resize

from src.augmentation.cutmix import Cutmix
from src.augmentation.mixup import Mixup
from src.models.base import BaseModel
from src.models.decoder.newunet import ResAttnUNet1DDecoder
from src.models.feature_extractor.spectrogram import SpecFeatureExtractor

class NewSpec2DCNN(BaseModel):
    def __init__(
        self,
        feature_extractor: nn.Module,
        decoder: nn.Module,
        encoder_name: str,
        in_channels: int,
        encoder_weights: Optional[str] = None,
        mixup_alpha: float = 0.5,
        cutmix_alpha: float = 0.5,
    ):
        super().__init__()
        self.feature_extractor = feature_extractor
        self.encoder = smp.Unet(
            encoder_name=encoder_name,
            encoder_weights=encoder_weights,
            in_channels=in_channels,
            classes=1,
        )
        self.decoder = decoder
        self.mixup = Mixup(mixup_alpha)
        self.cutmix = Cutmix(cutmix_alpha)
        self.loss_fn = nn.BCEWithLogitsLoss()

    def _forward(
        self,
        x: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        do_mixup: bool = False,
        do_cutmix: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        x = self.feature_extractor(x)  # (batch_size, n_channels, height, n_timesteps)

        if do_mixup and labels is not None:
            x, labels = self.mixup(x, labels)
        if do_cutmix and labels is not None:
            x, labels = self.cutmix(x, labels)

        x = self.encoder(x).squeeze(1)  # (batch_size, height, n_timesteps)
        logits = self.decoder(x)  # (batch_size, n_timesteps, n_classes)

        if labels is not None:
            return logits, labels
        else:
            return logits

    def _logits_to_proba_per_step(self, logits: torch.Tensor, org_duration: int) -> torch.Tensor:
        preds = logits.sigmoid()
        return resize(preds, size=[org_duration, preds.shape[-1]], antialias=False)[:, :, [1, 2]]

    def _correct_labels(self, labels: torch.Tensor, org_duration: int) -> torch.Tensor:
        return resize(labels, size=[org_duration, labels.shape[-1]], antialias=False)[:, :, [1, 2]]


# # Assuming you have the necessary feature_extractor and other configurations
# feature_extractor = SpecFeatureExtractor(height=, out_chans=)
# decoder = ResAttnUNet1DDecoder(n_channels=…, n_classes=…, duration=…)
# model = Spec2DCNN(feature_extractor=feature_extractor, decoder=decoder, encoder_name=…, in_channels=…, encoder_weights=…)